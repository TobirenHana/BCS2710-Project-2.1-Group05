"""Regression tests for instrumentation and the unfiltered tracker path."""
import csv
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from benchmark import BenchmarkLogger
from facelandmarker_input import FaceLandmarkerInputProvider, EYE_CORNERS
from normalized_input import NormalizedInput
from one_euro_filter import OneEuroFilter
from run_tracking_tests import aggregate, comparisons, historical, summarize


class BenchmarkTests(unittest.TestCase):
    def test_logger_columns_and_blank_baseline(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "test.csv"
            logger = BenchmarkLogger(p, "scripted")
            logger.log_frame(.02, .003)
            logger.close()
            with p.open(newline="") as file:
                row = next(csv.DictReader(file))
            self.assertEqual(float(row["fps"]), 50)
            self.assertEqual(float(row["input_to_render_ms"]), 3)
            self.assertEqual(row["tracking_found"], "")
            self.assertNotIn(None, row)

    def test_summary_uses_frame_times_and_separate_detection_denominator(self):
        data = [{"frame_time_ms": "10", "tracking_found": "1", "auto_calibrated": "1"},
                {"frame_time_ms": "30", "tracking_found": "0", "auto_calibrated": "1"}]
        detections = [{"face_found": "1", "detector_ms": "3"}, {"face_found": "1", "detector_ms": "5"},
                      {"face_found": "0", "detector_ms": "7"}]
        result = summarize(data, detections, 1)
        self.assertEqual(result["fps"], 50)
        self.assertEqual(result["p95_frame_ms"], 30)
        self.assertEqual(result["render_valid_pct"], 50)
        self.assertAlmostEqual(result["detection_pct"], 200/3)
        self.assertEqual(result["detector_ms"], 5)

    def test_historical_import_accepts_only_scripted_python_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            (folder / "old.csv").write_text(
                "input_mode,input_to_render_ms,frame_time_ms,test,object_count,parallax_enabled,run\n"
                "scripted,2,20,basic,3,1,1\n"
                "tracker,3,25,basic,3,1,1\n", encoding="utf-8")
            (folder / "unrelated.csv").write_text("test,frame_time_ms\nbasic,16\n", encoding="utf-8")
            results = historical(folder)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["fps"], 50)
            self.assertEqual(results[0]["input_render_ms"], 2)

    def test_paired_delta(self):
        base = dict(test="basic", objects=3, parallax="on", fps=60, frame_ms=16, mode="scripted")
        tracked = dict(base, fps=55, frame_ms=18, mode="tracker")
        result = comparisons(aggregate([base, tracked], ("mode", "test", "objects", "parallax")))[0]
        self.assertEqual(result["delta_fps"], -5)
        self.assertEqual(result["delta_frame_ms"], 2)
        self.assertIsNone(result["delta_cpu_pct"])

    def test_capped_and_uncapped_are_separate_pairs(self):
        base = dict(test="basic", objects=3, parallax="on", fps=60, mode="scripted", fps_cap=60)
        data = [base, dict(base, mode="tracker", fps=59),
                dict(base, fps_cap=0, fps=200), dict(base, fps_cap=0, mode="tracker", fps=150)]
        result = comparisons(aggregate(data, ("mode", "test", "objects", "parallax", "fps_cap")))
        self.assertEqual({r["fps_cap"]: r["delta_fps"] for r in result}, {60: -1, 0: -50})


class FilterTests(unittest.TestCase):
    def test_filter_reduces_alternating_stationary_noise(self):
        f = OneEuroFilter(min_cutoff=1, beta=2)
        raw = [0.02 * (-1)**i for i in range(120)]
        filtered = [f.filter(v, i/30) for i, v in enumerate(raw)]
        self.assertLess(sum(abs(v) for v in filtered[10:]), sum(abs(v) for v in raw[10:]))
        f.reset()
        self.assertEqual(f.filter(.5, 10), .5)

    def test_unfiltered_worker_publishes_valid_face(self):
        # Exercise the real worker loop with a mocked camera and detector.
        provider = FaceLandmarkerInputProvider.__new__(FaceLandmarkerInputProvider)
        provider._cv2 = SimpleNamespace(COLOR_BGR2RGB=1, cvtColor=lambda frame, _: frame)
        provider._mp = SimpleNamespace(ImageFormat=SimpleNamespace(SRGB=1), Image=lambda **kw: kw)
        provider._cap = SimpleNamespace(read=lambda: (True, object()))
        provider._lock = threading.Lock()
        provider._running = True
        provider.video_path = None
        provider._latest = None
        provider.telemetry = []
        provider.error = None
        provider.ids = EYE_CORNERS
        provider.mirror = True
        provider.max_age_seconds = 1
        provider.filter_enabled = False
        provider.log_tracking = False
        provider.filter_x = OneEuroFilter()
        provider.filter_y = OneEuroFilter()
        def detect(*_):
            provider._running = False
            return SimpleNamespace(face_landmarks=[[SimpleNamespace(x=.25, y=.75)] * 478])
        provider._landmarker = SimpleNamespace(detect_for_video=detect)
        provider._run()
        self.assertIsNone(provider.error)
        state = NormalizedInput()
        self.assertTrue(provider.update(state))
        self.assertEqual(state.get_position(), (.5, .5))
        self.assertEqual(len(provider.telemetry), 1)
        self.assertEqual(provider.telemetry[0][2], 1)


if __name__ == "__main__":
    unittest.main()
