"""Deterministic, frame-based debug input for the parallax prototype."""

import math

from normalized_input import NormalizedInput


class ScriptedInputProvider:
    """Repeat a figure-eight path every 600 updates, starting at center."""

    CYCLE_FRAMES = 600

    def __init__(self):
        self._frame = 0

    def update(self, input_state: NormalizedInput) -> None:
        """Write one normalized sample and advance by one frame."""
        phase = math.tau * self._frame / self.CYCLE_FRAMES
        input_state.set_position(math.sin(phase), math.sin(2.0 * phase))
        self._frame = (self._frame + 1) % self.CYCLE_FRAMES
