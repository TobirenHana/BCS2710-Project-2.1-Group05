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
