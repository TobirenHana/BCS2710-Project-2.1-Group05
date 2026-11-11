"""Run with: python -m unittest discover -s python_benchmark_ready -p 'test_*.py'."""

import unittest

from normalized_input import NormalizedInput
from simulated_input import SimulatedInputProvider


class SimulatedInputTests(unittest.TestCase):
    def collect(self, provider, count):
        state = NormalizedInput()
        samples = []
        for _ in range(count):
            provider.update(state)
            samples.append(state.get_position())
        return samples

    def test_repeatable_bounded_cycle(self):
        length = SimulatedInputProvider.CYCLE_FRAMES
        samples = self.collect(SimulatedInputProvider(), length * 2)
        self.assertEqual(samples[:length], samples[length:])
        self.assertEqual(samples[:length], self.collect(SimulatedInputProvider(), length))
        self.assertTrue(all(-1.0 <= value <= 1.0 for point in samples for value in point))

    def test_center_and_cardinal_positions_are_held(self):
        samples = self.collect(SimulatedInputProvider(), 1080)
        self.assertEqual(samples[0], (0.0, 0.0))
        for start, position in [(180, (-1.0, 0.0)), (420, (1.0, 0.0)),
                                (660, (0.0, -1.0)), (900, (0.0, 1.0))]:
            self.assertEqual(samples[start:start + 60], [position] * 60)
        self.assertEqual(samples[-1], (0.0, 0.0))

    def test_pause_preserves_sample_and_resume_continues_sequence(self):
        provider = SimulatedInputProvider()
        before = self.collect(provider, 140)
        provider.toggle_pause()
        self.assertEqual(self.collect(provider, 20), [before[-1]] * 20)
        provider.toggle_pause()
        reference = self.collect(SimulatedInputProvider(), 141)
        self.assertEqual(self.collect(provider, 1), reference[140:])

    def test_restart_resumes_from_center(self):
        provider = SimulatedInputProvider()
        self.collect(provider, 200)
        provider.toggle_pause()
        provider.reset()
        self.assertFalse(provider.paused)
        self.assertEqual(self.collect(provider, 180), self.collect(SimulatedInputProvider(), 180))


if __name__ == "__main__":
    unittest.main()
