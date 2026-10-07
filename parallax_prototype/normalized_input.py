"""Tracking-to-parallax coordinates, independent of Pygame."""

import math


class NormalizedInput:
    """Store x/y floats: -1 is left/top, 0 is center, +1 is right/bottom."""

    def __init__(self, x: float = 0.0, y: float = 0.0):
        self.set_position(x, y)

    @staticmethod
    def _clamp(value: float) -> float:
        value = float(value)
        # NaN has no direction; use center. Infinities clamp to an edge.
        if math.isnan(value):
            return 0.0
        return max(-1.0, min(1.0, value))

    def set_position(self, x: float, y: float) -> None:
        """Accept a tracking/debug sample and clamp each axis to [-1, 1]."""
        position = (self._clamp(x), self._clamp(y))
        self._position = position

    def get_position(self) -> tuple[float, float]:
        """Return the latest clamped sample, without applying smoothing."""
        return self._position
