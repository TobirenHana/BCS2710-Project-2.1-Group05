# Automated parallax and face tracking evaluation

Copy these files into the existing `python_benchmark_ready` directory. This suite tests only the Python/Pygame prototype. It updates benchmark logging and the tracker adapter, leaving the scene rendering and config unchanged.

## Windows commands (run in python_benchmark_ready)

Use a Python environment that supports pygame-ce, OpenCV and MediaPipe (Python 3.12 is a sensible option if your current interpreter cannot install them).

```powershell
py -m pip install -r requirements.txt -r requirements-tracking.txt
py -m unittest discover -v
py record_test_video.py face.mp4
py run_tracking_tests.py --video face.mp4 --quick
```

The recorder asks you to remain centered for five seconds, then move slowly left, right, up and down, keeping your face visible. Check the recording before using it. For rigorous comparisons keep the same video, display resolution, machine, power mode and application settings; close unrelated programs and do not minimize the Pygame window. Video replay uses real MediaPipe inference, not a fake detector. The video loops at its encoded frame rate; if processing cannot keep up, replay slows rather than skipping source frames. The first run downloads the model if it is absent; internet access is required for that download.

Full benchmark (66 runs: 42 capped and 24 uncapped; about 95.5 minutes of warmup/recording plus startup):

```powershell
py run_tracking_tests.py --video face.mp4
```

Optional no-face negative control: record an empty scene, then use the same runner with `--no-face-video`:

```powershell
py record_test_video.py empty.mp4 --empty
py run_tracking_tests.py --video face.mp4 --no-face-video empty.mp4 --quick
```

Alternatively `py run_tracking_tests.py --live --quick` uses a live webcam and is not fully repeatable. `--camera 1` selects another camera. A full live suite requires someone in front of the camera for each tracker run. Use `--baseline-only` to run fresh scripted Python benchmarks without a webcam or MediaPipe. Add `--old-python PATH` to import historical scripted Python frame CSVs from a directory, if available.

## Test matrix

Each case is run three times per input mode, alternating order. Resolution comes from the existing config (1280x720). The runner explicitly selects a 60 FPS cap and repeats basic/complexity at cap 0 (uncapped). Use --fps-cap 60 for the capped suite only or --fps-cap 0 for uncapped basic/complexity only. All normal tests record 60 s, stability records 300 s, and all use a 5 s warmup. `--quick` runs only the basic pair for 10 s each. No-face control is a separate additional run.

| Case | Objects setting | Parallax | Recording |
|---|---:|---|---:|
| Basic | 3 | On | 60 s |
| Complexity | 5, 20, 50 | On | 60 s each |
| Parallax | 3 | On / Off | 60 s each |
| Stability | 3 | On | 300 s |

The existing renderer interprets --objects as total objects (three baseline objects plus N-3 primitives), although the report describes the counts as extra objects. We preserve the original CLI values for historical comparison; verify which convention was used in the historical runs. The existing renderer's objects setting controls extra benchmark primitives; `off` disables layer motion but retains lighting updates (existing behavior). Scripted input is the existing figure-eight trajectory, whereas tracker input comes from the video. Therefore this estimates total practical tracking integration overhead, not the isolated cost under exactly identical trajectories. Compare older Python runs only when the hardware, settings, and metric definitions match. Matching capped FPS does not imply equal computational cost.

## Output

Each run prints a summary. A timestamped `tracking_results` folder contains:

- `report.txt`: readable Python paired results.
- `comparison.csv`: paired means and tracker-minus-scripted deltas.
- `summary.csv` and `runs.csv`: condition-level and individual-run statistics.
- `historical_vs_current.csv`: optional side-by-side historical and current Python metrics.
- `historical_python_summary.csv`, `historical_python_runs.csv`: optional imported Python CSV aggregation.
- `unit_tests.txt`: executed functional test output.
- Per-run CSVs: original frame metrics plus freshness, calibration, coordinates and software sample-to-flip latency.
- `*.tracking.csv`: one row per detector result, including missing faces, raw and filtered coordinates and inference-pipeline timing. No duplicated samples from the renderer's 60 FPS loop.
- `metadata.json`: OS, package versions, config and video SHA-256 hashes.

FPS = 1000 / mean frame time; P95 uses nearest-rank percentile. Per-condition means weight each run equally. CPU is process CPU percent (can exceed 100%); RSS is resident process memory. Detector time includes conversion to RGB and MediaPipe inference, measured after a successful frame read. Detector FPS is processed frames per recording second. Detection % is the fraction of processed frames with a face; render-valid % is the fraction of render frames with a fresh face sample. Calibration % is the fraction of render frames marked calibrated. Sample-to-flip latency starts after frame acquisition and ends when display.flip returns; it is not physical motion-to-photon latency. No-face control reports the fraction of processed frames without a detection, assuming the clip really contains no faces. A visible-face-only clip permits interpreting detection rate as frame-level recall, but it is not landmark localization accuracy. For accuracy, annotate ground-truth positions; for motion-to-photon latency use external measurement hardware.

Existing unit tests cover coordinate mapping, calibration, stale samples, simulated motion and tracking loss/recovery. Added tests cover logging, summary math, comparison deltas, smoothing, and a regression for the disabled-filter path. The actual webcam/MediaPipe/render benchmarks must run locally. The supplied Python folder did not contain old Python benchmark CSVs, a recorded face video or a model. Historical aggregate results were transcribed from Project_Plan_II(1).pdf, tables 1–4 and stability paragraph, in historical_report_python.csv. The runner writes report_baseline_vs_current.csv and prints the descriptive comparison automatically. Blank cells mean not reported. The old report calls 5/20/50 extra objects, whereas the original Python code uses total counts. Old FPS calculation and exact settings are unverified; fresh paired runs are the primary evidence. No Godot results are used.

The supplied historical_face_landmarker.csv also lists the standalone tracking results from Table 5. The runner writes standalone_vs_integrated_detector.csv for descriptive processing-time comparisons. Different clips, timing boundaries, standalone versus integrated memory and CPU, and estimated versus measured FPS prevent treating these as identical conditions.
