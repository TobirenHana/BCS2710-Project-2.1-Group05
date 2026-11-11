"""Guided simulated observer positions; no camera or tracker required."""

from normalized_input import NormalizedInput


class SimulatedInputProvider:
    """Repeat a fixed center/left/right/top/bottom demonstration by frame."""

    STAGES = (
        ("Center", (0.0, 0.0)),
        ("Left", (-1.0, 0.0)),
        ("Center", (0.0, 0.0)),
        ("Right", (1.0, 0.0)),
        ("Center", (0.0, 0.0)),
        ("Top", (0.0, -1.0)),
        ("Center", (0.0, 0.0)),
        ("Bottom", (0.0, 1.0)),
        ("Center", (0.0, 0.0)),
    )
    MOVE_FRAMES = 60
    HOLD_FRAMES = 60
    CYCLE_FRAMES = len(STAGES) * (MOVE_FRAMES + HOLD_FRAMES)

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        """Restart at center and resume playback."""
        self._frame = 0
        self._position = (0.0, 0.0)
        self.stage = "Hold Center"
        self.paused = False

    def toggle_pause(self) -> None:
        self.paused = not self.paused

    def update(self, input_state: NormalizedInput) -> None:
        """Write one sample through the shared interface, then advance."""
        if not self.paused:
            stage_index, step = divmod(self._frame, self.MOVE_FRAMES + self.HOLD_FRAMES)
            name, destination = self.STAGES[stage_index]
            _, origin = self.STAGES[stage_index - 1]
            progress = min((step + 1) / self.MOVE_FRAMES, 1.0)
            # Smooth transitions with zero velocity at the endpoints.
            blend = progress * progress * (3.0 - 2.0 * progress)
            self._position = tuple(
                start + (end - start) * blend
                for start, end in zip(origin, destination)
            )
            self.stage = ("Moving to " if step < self.MOVE_FRAMES - 1 else "Hold ") + name
            self._frame = (self._frame + 1) % self.CYCLE_FRAMES
        input_state.set_position(*self._position)
