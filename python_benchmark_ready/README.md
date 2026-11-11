# 2.5D Parallax Prototype (BCS2710)

Minimal 2.5D layered parallax prototype for Phase 1 baseline evaluation.

## Requirements
- Python 3.x
- pygame-ce
- psutil (benchmark CPU/memory measurements)

Run: pip install -r requirements.txt

## Running
Run: python3 parallax_system.py

All parameters can be configured inside config.json.

## Input modes

Run these commands from `python_benchmark_ready/`:

- Mouse debug mode (default): `python3 parallax_system.py`
  or `python3 parallax_system.py --input-mode mouse`.
- Scripted mode: `python3 parallax_system.py --input-mode scripted`.
- Guided simulated demo: `python3 parallax_system.py --input-mode simulated`.

`ScriptedInputProvider` in `scripted_input.py` writes a normalized sample through
`NormalizedInput.set_position(x, y)` once per frame. It starts at center and
follows a figure-eight path: `x = sin(phase)`, `y = sin(2 * phase)`.
The sequence repeats exactly every 600 frames (approximately 10 seconds at
60 FPS). Each run starts at frame zero and produces the same sample sequence.
There is no randomness or wall-clock dependency; changing FPS changes playback
speed, not the coordinates at a given frame. Mouse movement has no effect in
scripted mode. Both modes use the existing smoothing and rendering.

## Meeting demo without a tracker

On Windows, double-click `run_simulated_demo.cmd` to start the demo.
It uses the Python installation on PATH and requires `pygame-ce`.

From PowerShell, run:

```powershell
cd "C:\Users\evang\Desktop\BCS2710-Project-2.1-Group05\python_benchmark_ready"
python parallax_system.py --input-mode simulated
```

This mode simulates observer position; it does not detect a face, use a webcam,
or validate the accuracy of a real tracker. The window explicitly labels it
`SIMULATED INPUT - NO WEBCAM TRACKING` and shows the current input x/y, movement
stage, and playback status.

The repeatable sequence is center, left, center, right, center, top, center,
bottom, center. Each stage has a 60-frame smooth transition and a 60-frame hold;
one cycle is 1080 frames (about 18 seconds at 60 FPS). Left/right use x=-1/+1;
top/bottom use y=-1/+1. Playback is frame-based, so slower FPS slows the demo
without changing its sample sequence. Positions use the existing
`NormalizedInput` interface, smoothing, and scene rendering.

- **Space** pauses/resumes the simulated input. Rendering continues, including
  the existing smoothing settling toward the held position.
- **C** sets the current valid position as the new center.
- **X** clears the calibration and resets input handling.
- **L** toggles simulated tracking loss/recovery (simulated mode only).
- **R** restarts from center, clears calibration/loss, and resumes playback.
- **Esc** exits.

For a short presentation: show one automatic cycle, pause during a side hold
to point out the different layer offsets, then press R to repeat the sequence.
Explain: "This is simulated position input driving the real parallax renderer;
live webcam tracking is not connected yet."

## Center calibration and tracking loss

`tracking_input.py` contains one small `TrackingInput` class. Its main variables
are the saved center, current output x/y, and the time spent without tracking.
Mouse and scripted inputs are valid by default. The original scene calculations
and layer smoothing are unchanged.

Press **C** to save the current raw x/y as the center. The calculation is simply
`output = raw - center`, clamped to [-1, 1]. For example, calibrating at x=0.4
makes raw x=0.4 become output x=0.0, and raw x=0.6 become output x=0.2.
This shifts the center; it does not rescale the movement range. Calibration is
ignored while tracking is unavailable. **X** clears the saved center.

When `tracking_found` is false, the handler ignores raw coordinates. It holds
the last output for `tracking_hold_seconds` (default 0.5 in `config.json`), then
gradually returns toward zero. When a valid position returns, it eases toward
that position while keeping the saved calibration. These timings use elapsed
seconds from `time.perf_counter()`, even when simulated playback is paused.

Try this demonstration:

1. Start simulated mode and wait until it holds Left or Right.
2. Press Space to pause, then C. The scene settles at center even though the
   raw position is off-center. X removes this calibration.
3. With the raw position held off-center, press L. Watch the status change
   from `Holding last position` to `Returning to center`.
4. Press L again. `Recovering` eases back to the position; C is available again.
5. R resets the entire simulated demonstration.

The layers still use their original smoothing, so they settle over a few frames.
Raw position, handled output, saved center, and tracking status are shown on
screen. L only simulates a detection failure: no actual camera is connected.

For future tracking integration, set `tracking_found` from each detection result.
Missing or stale detections must be marked false by the tracker adapter; this
handler cannot discover a frozen tracker on its own. Feed a valid normalized
sample into `raw_input` and let the same handler process it.

Optional CSV logging works with this mode too:

```powershell
python parallax_system.py --input-mode simulated --benchmark
```

The benchmark includes the demo overlay in frame time, but excludes it from
input-to-render time. Paused frames are logged too; restart only resets the
simulated movement, not the CSV frame index. For uninterrupted comparison runs,
avoid pause/restart, calibration, and simulated loss, and use the same input
mode for all runs. CSV rows do not record these keyboard actions.

Run the provider tests from the repository root:

```powershell
python -m unittest discover -s python_benchmark_ready -p "test_*.py"
```

## Benchmark logging

Benchmarking is optional and works with all input modes:

```sh
python3 parallax_system.py --benchmark
python3 parallax_system.py --input-mode scripted --benchmark scripted_run.csv
```

`--benchmark` creates a unique `benchmark_*.csv` in the current directory.
An optional path selects the output file; existing files are never overwritten.
Without the flag, no CSV is opened or written. Rows are buffered during the run
and flushed when the file closes on normal exit, including Escape.
The file also closes during interpreter shutdown after an unhandled exception.

The team's benchmark controls are preserved: `--test`, `--objects`,
`--parallax`, `--warmup`, `--duration`, and `--run`. When benchmarking, the
default is a 5-second warmup followed by 60 seconds of recording, then exit.
For an uninterrupted meeting demo, omit `--benchmark`. See `RUN_TESTS.txt`
for the team's experiment commands.

All durations use `time.perf_counter()`. Each CSV row contains:

| Column | Meaning |
| --- | --- |
| `frame_index` | Zero-based frame number for this run. |
| `input_mode` | `mouse`, `scripted`, or `simulated`. |
| `elapsed_s`, `test`, `run` | Recording elapsed time and experiment identifiers. |
| `object_count`, `parallax_enabled` | Scene complexity and parallax setting. |
| `frame_time_ms` | From loop entry through return of `pygame.display.flip()`: events, input provider, parallax calculations, drawing, FPS cap wait, and overlay. Excludes the subsequent CSV write. |
| `fps` | Instantaneous FPS: `1000 / frame_time_ms`, rather than the overlay's averaged Pygame FPS. |
| `input_to_render_ms` | From immediately before raw normalized input retrieval through the final scene blit: retrieval, calibration/loss handling, smoothing, layer offsets, shadow calculations, and scene drawing. Excludes input generation, FPS cap wait, overlay, display flip, and CSV writing. |
| `cpu_percent`, `memory_mb` | Process resource samples from psutil; blank if psutil is unavailable. |

These are CPU-side timings. They do not measure physical display presentation
or webcam/tracking processing. Logging has some overhead. The existing visual
overlay is preserved; its `Loop Time` value still measures loop entry
through the FPS cap wait and is separate from `input_to_render_ms`.

## Tracking-to-parallax interface

`normalized_input.py` provides `NormalizedInput`, with no Pygame dependency.
Call `set_position(x, y)` with floats; `get_position()` returns the latest
clamped `(x, y)` sample. The initial sample is `(0.0, 0.0)`.

| Axis | -1.0 | 0.0 | +1.0 |
| --- | --- | --- | --- |
| x | Left | Center | Right |
| y | Top | Center | Bottom |

Out-of-range values (including infinities) clamp to the nearest edge.
NaN maps to center on the affected axis. Values must be convertible to floats;
other values raise `TypeError` or `ValueError`.

The main loop selects the mouse adapter, `scripted_input.update(raw_input)`,
or `simulated_input.update(raw_input)`. The raw sample then passes through
`TrackingInput` before being stored in `input_state` for rendering.
To integrate a future tracker, replace the input selection each frame:

```python
tracking_found = detection_is_valid  # False if no fresh position is available.
if tracking_found:
    raw_input.set_position(tracker_x, tracker_y)
# The existing loop then applies calibration/loss handling and renders.
```

Rendering reads only the normalized sample. Layer movement retains its existing
0.2 smoothing, while shadow lighting uses the unsmoothed sample converted back
to screen coordinates. No webcam or face tracking is implemented.
