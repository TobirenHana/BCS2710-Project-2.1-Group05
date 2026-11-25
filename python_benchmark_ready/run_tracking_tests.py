"""Repeat the original benchmark matrix with and without real face tracking."""
import argparse
import csv
import hashlib
import json
import math
import platform
import statistics as stats
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = [("basic", 3, "on"), *( ("complexity", n, "on") for n in (5, 20, 50)),
         ("parallax", 3, "on"), ("parallax", 3, "off"), ("stability", 3, "on")]
REPORT_BASELINE = HERE / "historical_report_python.csv"


def rows(path):
    with path.open(newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def values(data, key):
    return [float(r[key]) for r in data if r.get(key, "") not in ("", None)
            and math.isfinite(float(r[key]))]


def mean(seq):
    return stats.mean(seq) if seq else None


def percentile(seq, p):
    if not seq:
        return None
    seq = sorted(seq)
    return seq[math.ceil(p * len(seq)) - 1]


def summarize(data, tracking=(), elapsed=None):
    frame = values(data, "frame_time_ms")
    if not frame or sum(frame) <= 0:
        raise ValueError("No valid frame timings")
    result = {
        "frames": len(frame), "fps": 1000 * len(frame) / sum(frame),
        "frame_ms": mean(frame), "p95_frame_ms": percentile(frame, .95),
        "frame_sd_ms": stats.pstdev(frame), "over_33ms_pct": 100 * sum(x > 33.33 for x in frame) / len(frame),
        "cpu_pct": mean(values(data, "cpu_percent")), "memory_mb": mean(values(data, "memory_mb")),
        "input_render_ms": mean(values(data, "input_to_render_ms")),
    }
    found = values(data, "tracking_found")
    if found:
        faces = values(tracking, "face_found")
        result.update(render_valid_pct=100 * mean(found), detection_pct=100 * mean(faces) if faces else None,
                      detector_frames=len(faces), detector_fps=len(faces) / elapsed if elapsed else None,
                      detector_ms=mean(values(tracking, "detector_ms")),
                      detector_sd_ms=stats.pstdev(values(tracking, "detector_ms")) if values(tracking, "detector_ms") else None,
                      p95_detector_ms=percentile(values(tracking, "detector_ms"), .95),
                      sample_age_ms=mean(values(data, "sample_age_ms")),
                      sample_flip_ms=mean(values(data, "sample_to_flip_ms")),
                      p95_sample_flip_ms=percentile(values(data, "sample_to_flip_ms"), .95),
                      calibration_pct=100 * mean(values(data, "auto_calibrated")))
    return result


def save_csv(path, data):
    if not data:
        return
    fields = list(dict.fromkeys(k for row in data for k in row))
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fields)
        writer.writeheader()
        writer.writerows({k: round(v, 4) if isinstance(v, float) else v for k, v in row.items()} for row in data)


def group_key(row):
    return row["test"], int(row["object_count"]), "on" if str(row["parallax_enabled"]).lower() in ("1", "true", "on") else "off"


def historical(folder):
    """Import only Python frame CSVs from the user's earlier runs."""
    results = []
    if folder is None:
        return results
    for path in sorted(folder.rglob("*.csv")):
        data = rows(path)
        if not data or not {"input_mode", "input_to_render_ms", "frame_time_ms", "test", "object_count", "parallax_enabled"}.issubset(data[0]):
            continue
        groups = defaultdict(list)
        for r in data:
            if r["input_mode"] != "scripted":
                continue
            groups[(*group_key(r), r.get("run", "1"))].append(r)
        for (test, n, enabled, run), group in groups.items():
            results.append(dict(test=test, objects=n, parallax=enabled,
                                run=run, source=str(path), **summarize(group)))
    if not results:
        raise ValueError("No compatible scripted Python frame CSVs found in " + str(folder))
    return results


def aggregate(data, keys):
    groups = defaultdict(list)
    for r in data:
        groups[tuple(r[k] for k in keys)].append(r)
    output = []
    for group, runs in groups.items():
        row = dict(zip(keys, group), runs=len(runs))
        for key in dict.fromkeys(k for r in runs for k in r):
            if key in keys or key in ("run", "source", "expected_face"):
                continue
            nums = [r[key] for r in runs if isinstance(r.get(key), (int, float))]
            if nums:
                row[key] = mean(nums)
        row["between_run_fps_sd"] = stats.stdev([r["fps"] for r in runs]) if len(runs) > 1 else None
        output.append(row)
    return output


def comparisons(grouped):
    pairs = defaultdict(dict)
    for r in grouped:
        pairs[(r["test"], r["objects"], r["parallax"], r.get("fps_cap", 60))][r["mode"]] = r
    result = []
    for (test, n, enabled, cap), modes in pairs.items():
        if "scripted" not in modes or "tracker" not in modes:
            continue
        a, b = modes["scripted"], modes["tracker"]
        row = dict(test=test, objects=n, parallax=enabled, fps_cap=cap, baseline_runs=a["runs"], tracker_runs=b["runs"])
        for key in ("fps", "frame_ms", "p95_frame_ms", "cpu_pct", "memory_mb", "input_render_ms"):
            x, y = a.get(key), b.get(key)
            row.update({"baseline_" + key: x, "tracker_" + key: y,
                        "delta_" + key: y - x if x is not None and y is not None else None})
        row.update({k: b.get(k) for k in ("detection_pct", "render_valid_pct", "detector_ms", "detector_sd_ms", "p95_detector_ms", "detector_fps", "sample_flip_ms", "calibration_pct")})
        result.append(row)
    return result


def fmt(x):
    return "N/A" if x is None else f"{x:.2f}"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    src = p.add_mutually_exclusive_group()
    src.add_argument("--video", type=Path, help="Repeatable face video, preferably 640x480 / 30 FPS")
    src.add_argument("--live", action="store_true", help="Use a real webcam; not fully repeatable")
    p.add_argument("--camera", type=int, default=0)
    p.add_argument("--no-face-video", type=Path, help="Optional negative control containing no faces")
    p.add_argument("--quick", action="store_true", help="Basic test only, 10 seconds, one run")
    p.add_argument("--fps-cap", choices=("both", "60", "0"), default="both", help="Default: capped suite plus uncapped basic/complexity tests")
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--duration", type=float, default=60)
    p.add_argument("--stability-duration", type=float, default=300)
    p.add_argument("--warmup", type=float, default=5)
    src.add_argument("--baseline-only", action="store_true", help="Run scripted Python benchmarks only")
    p.add_argument("--old-python", type=Path, help="Folder with previous Python scripted frame CSVs")
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    if not (args.video or args.live or args.baseline_only):
        p.error("Choose --video FILE, --live or --baseline-only")
    if min(args.runs, args.duration, args.stability_duration) <= 0 or args.warmup < 0:
        p.error("Invalid test durations or repetitions")
    for video in (args.video, args.no_face_video):
        if video and not video.is_file():
            p.error(f"Missing video: {video}")
    out = (args.output or HERE / "tracking_results" / datetime.now().strftime("%Y%m%d_%H%M%S_%f")).resolve()
    out.mkdir(parents=True, exist_ok=False)
    old = historical(args.old_python)
    old_groups = aggregate(old, ("test", "objects", "parallax"))
    save_csv(out / "historical_python_runs.csv", old)
    save_csv(out / "historical_python_summary.csv", old_groups)
    report = ["PYTHON / PYGAME BENCHMARK RESULTS", "Historical Python runs: " + str(len(old))]
    if not old:
        report.append("No historical raw Python CSVs supplied; historical report summary is compared separately, if available.")
    print("\n".join(report), flush=True)
    import importlib.metadata as metadata
    config = json.loads((HERE / "config.json").read_text())
    meta = dict(platform=platform.platform(), processor=platform.processor(), python=sys.version,
                config=config, args={k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}, packages={})
    for package in ("pygame-ce", "psutil", "mediapipe", "opencv-python"):
        try:
            meta["packages"][package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            meta["packages"][package] = "missing"
    for key in ("video", "no_face_video"):
        path = getattr(args, key)
        if path:
            with path.open("rb") as f:
                meta[key + "_sha256"] = hashlib.file_digest(f, "sha256").hexdigest()
    (out / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    unit = subprocess.run([sys.executable, "-m", "unittest", "discover", "-v"], cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    (out / "unit_tests.txt").write_text(unit.stdout, encoding="utf-8")
    print(unit.stdout, flush=True)
    unit.check_returncode()
    runs = []
    cases = CASES[:1] if args.quick else CASES
    count = 1 if args.quick else args.runs

    def execute(test, n, enabled, run, mode, video, seconds, expected=None, cap=60):
        name = f"{test}_{n}_{enabled}_cap{cap}_{mode}_{run}"
        path = out / (name + ".csv")
        actual_mode = "scripted" if mode == "scripted" else "tracker"
        cmd = [sys.executable, "parallax_system.py", "--input-mode", actual_mode,
               "--test", test, "--objects", str(n), "--parallax", enabled, "--run", str(run),
               "--fps-cap", str(cap), "--duration", str(seconds), "--warmup", str(args.warmup), "--benchmark", str(path)]
        if actual_mode == "tracker":
            cmd += ["--video", str(video.resolve())] if video else ["--camera", str(args.camera)]
        print(f"\nRunning {name} ({seconds}s recording)", flush=True)
        subprocess.run(cmd, cwd=HERE, check=True, timeout=seconds + args.warmup + 180)
        data = rows(path)
        elapsed = float(data[-1]["elapsed_s"]) if data else 0
        if elapsed < seconds - .1:
            raise RuntimeError(f"Incomplete run: {name} ({elapsed}s)")
        tracking = rows(path.with_suffix(".tracking.csv")) if actual_mode == "tracker" else []
        if actual_mode == "tracker" and not tracking:
            raise RuntimeError(f"No processed camera frames in {name}")
        r = dict(test=test, objects=n, parallax=enabled, run=run, mode=mode, expected_face=expected, fps_cap=cap,
                 **summarize(data, tracking, elapsed))
        if expected is not None:
            r["expected_class_match_pct"] = r["detection_pct"] if expected else 100-r["detection_pct"]
        runs.append(r)
        save_csv(out / "runs.csv", runs)
        print(f"FPS {fmt(r['fps'])} | frame {fmt(r['frame_ms'])} ms | CPU {fmt(r['cpu_pct'])}% | RAM {fmt(r['memory_mb'])} MB | face detection {fmt(r.get('detection_pct'))}%", flush=True)

    for run in range(1, count + 1):
        for test, n, enabled, cap in [(t, n, e, c) for c in ((60, 0) if args.fps_cap == "both" and not args.quick else (0,) if args.fps_cap == "0" else (60,)) for t, n, e in cases if c == 60 or t in ("basic", "complexity")]:
            seconds = 10 if args.quick else args.stability_duration if test == "stability" else args.duration
            # Alternate order to reduce systematic warm-cache/order bias.
            for mode in (("scripted",) if args.baseline_only else ("scripted", "tracker") if run % 2 else ("tracker", "scripted")):
                execute(test, n, enabled, run, mode, args.video, seconds, cap=cap)
    if args.no_face_video and not args.baseline_only:
        execute("basic", 3, "on", 1, "no_face_control", args.no_face_video, 10 if args.quick else args.duration, 0)
    grouped = aggregate(runs, ("mode", "test", "objects", "parallax", "fps_cap"))
    comparison = comparisons(grouped)
    save_csv(out / "summary.csv", grouped)
    save_csv(out / "comparison.csv", comparison)
    # Historical runs may differ in hardware/software; keep them separate.
    if old_groups:
        old_index = {(r["test"], r["objects"], r["parallax"]): r for r in old_groups}
        context = []
        for r in grouped:
            previous = old_index.get((r["test"], r["objects"], r["parallax"]))
            if previous and r["fps_cap"] == 60:
                merged = dict(r)
                for key in ("fps", "frame_ms", "p95_frame_ms", "cpu_pct", "memory_mb", "input_render_ms", "runs"):
                    merged["old_python_" + key] = previous.get(key)
                context.append(merged)
        save_csv(out / "historical_vs_current.csv", context)
    if REPORT_BASELINE.is_file():
        reported = {(r["test"], int(r["objects"]), r["parallax"], int(r["fps_cap"])): r for r in rows(REPORT_BASELINE)}
        save_csv(out / "historical_report_python.csv", list(reported.values()))
        context = []
        for r in grouped:
            old_row = reported.get((r["test"], r["objects"], r["parallax"], r["fps_cap"]))
            if not old_row or r["mode"] not in ("scripted", "tracker"):
                continue
            merged = dict(r, historical_source=old_row["source"])
            for key in ("fps", "p95_frame_ms", "memory_mb"):
                prior = float(old_row[key]) if old_row.get(key) else None
                current = r.get(key)
                merged["historical_" + key] = prior
                merged["delta_vs_historical_" + key] = current - prior if prior is not None and current is not None else None
            context.append(merged)
        save_csv(out / "report_baseline_vs_current.csv", context)
        report += ["", "HISTORICAL REPORT COMPARISON (descriptive; old FPS calculation/hardware may differ)"]
        for r in context:
            report.append(f"{r['test']} / {r['objects']} / cap {r['fps_cap']} / {r['parallax']} / {r['mode']}: old FPS {fmt(r['historical_fps'])}, new FPS {fmt(r['fps'])}, delta {fmt(r['delta_vs_historical_fps'])}; old P95 {fmt(r['historical_p95_frame_ms'])}, new P95 {fmt(r['p95_frame_ms'])}")
    if (HERE / "historical_face_landmarker.csv").is_file():
        previous_tracker = rows(HERE / "historical_face_landmarker.csv")
        save_csv(out / "historical_face_landmarker.csv", previous_tracker)
        prior = {r["metric"]: float(r["value"]) for r in previous_tracker}
        detector_context = []
        for r in grouped:
            if r["mode"] != "tracker":
                continue
            item = {k: r[k] for k in ("test", "objects", "parallax", "fps_cap")}
            item.update(old_standalone_mean_ms=prior["processing_mean"], integrated_mean_ms=r.get("detector_ms"),
                        old_standalone_sd_ms=prior["processing_sd"], integrated_sd_ms=r.get("detector_sd_ms"),
                        integrated_detector_fps=r.get("detector_fps"), integrated_detection_pct=r.get("detection_pct"))
            detector_context.append(item)
        save_csv(out / "standalone_vs_integrated_detector.csv", detector_context)
        report += ["", "STANDALONE VS INTEGRATED TRACKER (descriptive only; timing and video may differ)"]
        for r in detector_context:
            report.append(f"{r['test']} / {r['objects']} / cap {r['fps_cap']} / {r['parallax']}: old mean {fmt(r['old_standalone_mean_ms'])} ms; integrated mean {fmt(r['integrated_mean_ms'])} ms; actual detector FPS {fmt(r['integrated_detector_fps'])}")
    if args.baseline_only:
        report += ["", "SCRIPTED PYTHON BASELINE"]
        for r in grouped:
            report.append(f"{r['test']} / {r['objects']} / {r['parallax']}: FPS {fmt(r['fps'])}, frame {fmt(r['frame_ms'])} ms, CPU {fmt(r['cpu_pct'])}%, RAM {fmt(r['memory_mb'])} MB")
    report += ["", "PAIRED PYTHON COMPARISON (delta = tracker minus scripted)",
               f"{'Test':12} {'N':>3} {'Parallax':>8} {'Cap':>4} {'Base FPS':>9} {'Track FPS':>10} {'Delta ms':>9} {'Delta MB':>9} {'Face %':>8} {'Detect ms':>10}"]
    for r in comparison:
        report.append(f"{r['test']:12} {r['objects']:3} {r['parallax']:>8} {r['fps_cap']:4} {fmt(r['baseline_fps']):>9} {fmt(r['tracker_fps']):>10} {fmt(r['delta_frame_ms']):>9} {fmt(r['delta_memory_mb']):>9} {fmt(r['detection_pct']):>8} {fmt(r['detector_ms']):>10}")
    for r in runs:
        if r["mode"] == "no_face_control":
            report.append(f"No-face control: {fmt(r['expected_class_match_pct'])}% true-negative frames (assuming no faces in clip).")
    report += ["", "Detection percentage is not localization accuracy. Sample-to-flip is software-only latency.",
               "Compare older Python runs only if hardware, config and timing definitions match.",
               "Cap 0 = uncapped; CPU, frame time tails and memory may reveal overhead when capped FPS is unchanged."]
    text = "\n".join(report) + "\n"
    (out / "report.txt").write_text(text, encoding="utf-8")
    print(text)
    print(f"Results: {out}")


if __name__ == "__main__":
    main()
