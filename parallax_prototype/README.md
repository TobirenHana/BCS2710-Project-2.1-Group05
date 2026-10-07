# 2.5D Parallax Prototype (BCS2710)

Minimal 2.5D layered parallax prototype for Phase 1 baseline evaluation.

## Requirements
- Python 3.x
- pygame-ce

Run: pip install pygame-ce

## Running
Run: python3 parallax_system.py

All parameters can be configured inside config.json.

## Input modes

Run these commands from `parallax_prototype/`:

- Mouse debug mode (default): `python3 parallax_system.py`
  or `python3 parallax_system.py --input-mode mouse`.
- Scripted mode: `python3 parallax_system.py --input-mode scripted`.

`ScriptedInputProvider` in `scripted_input.py` writes a normalized sample through
`NormalizedInput.set_position(x, y)` once per frame. It starts at center and
follows a figure-eight path: `x = sin(phase)`, `y = sin(2 * phase)`.
The sequence repeats exactly every 600 frames (approximately 10 seconds at
60 FPS). Each run starts at frame zero and produces the same sample sequence.
There is no randomness or wall-clock dependency; changing FPS changes playback
speed, not the coordinates at a given frame. Mouse movement has no effect in
scripted mode. Both modes use the existing smoothing and rendering.

## Benchmark logging

Benchmarking is optional and works with either input mode:

```sh
python3 parallax_system.py --benchmark
python3 parallax_system.py --input-mode scripted --benchmark scripted_run.csv
```

`--benchmark` creates a unique `benchmark_*.csv` in the current directory.
An optional path selects the output file; existing files are never overwritten.
Without the flag, no CSV is opened or written. Rows are buffered during the run
and flushed when the file closes on normal exit, including Escape.
The file also closes during interpreter shutdown after an unhandled exception.

All durations use `time.perf_counter()`. Each CSV row contains:

| Column | Meaning |
| --- | --- |
| `frame_index` | Zero-based frame number for this run. |
| `input_mode` | `mouse` or `scripted`. |
| `frame_time_ms` | From loop entry through return of `pygame.display.flip()`: events, input provider, parallax calculations, drawing, FPS cap wait, and overlay. Excludes the subsequent CSV write. |
| `fps` | Instantaneous FPS: `1000 / frame_time_ms`, rather than the overlay's averaged Pygame FPS. |
| `input_to_render_ms` | From immediately before `NormalizedInput.get_position()` through the final scene blit: retrieval, smoothing, layer offsets, shadow calculations, and scene drawing. Excludes input generation, FPS cap wait, overlay, display flip, and CSV writing. |

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

The main loop selects either `update_mouse_input(input_state, WIDTH, HEIGHT)`
or `scripted_input.update(input_state)`. To integrate a future tracker, replace
that input selection with `input_state.set_position(tracker_x, tracker_y)`
each frame:

```python
input_state.set_position(-0.5, 0.25)  # Left of center, below center.
target_x, target_y = input_state.get_position()
```

Rendering reads only the normalized sample. Layer movement retains its existing
0.2 smoothing, while shadow lighting uses the unsmoothed sample converted back
to screen coordinates. No webcam or face tracking is implemented.
