"""Tests for the Face Landmarker adapter logic. No camera or mediapipe needed."""

import unittest
from types import SimpleNamespace

from facelandmarker_input import EYE_CORNERS, IRIS_CENTERS, evaluate_sample, landmarks_to_normalized
from tracking_input import TrackingInput


def fake_landmarks(x, y, count=478):
    """All landmarks at the same image position (MediaPipe range 0..1)."""
    return [SimpleNamespace(x=x, y=y) for _ in range(count)]


class LandmarkConversionTests(unittest.TestCase):
    def test_image_centre_is_zero(self):
        self.assertEqual(landmarks_to_normalized(fake_landmarks(0.5, 0.5)), (0.0, 0.0))

    def test_image_edges_map_to_plus_minus_one_without_mirror(self):
        self.assertEqual(landmarks_to_normalized(fake_landmarks(0.0, 0.0), mirror=False), (-1.0, -1.0))
        self.assertEqual(landmarks_to_normalized(fake_landmarks(1.0, 1.0), mirror=False), (1.0, 1.0))

    def test_mirror_flips_x_only(self):
        # Viewer moves to their right = left side of the raw camera image.
        x, y = landmarks_to_normalized(fake_landmarks(0.25, 0.75), mirror=True)
        self.assertAlmostEqual(x, 0.5)
        self.assertAlmostEqual(y, 0.5)

    def test_averages_only_the_selected_landmarks(self):
        landmarks = fake_landmarks(0.0, 0.0)
        for i, value in zip(EYE_CORNERS, (0.4, 0.5, 0.6, 0.7)):
            landmarks[i] = SimpleNamespace(x=value, y=value)
        x, y = landmarks_to_normalized(landmarks, EYE_CORNERS, mirror=False)
        self.assertAlmostEqual(x, 0.1)  # mean 0.55 -> (0.55 - 0.5) * 2
        self.assertAlmostEqual(y, 0.1)

    def test_iris_points_are_separate_from_eye_corners(self):
        landmarks = fake_landmarks(0.5, 0.5)
        for i in IRIS_CENTERS:
            landmarks[i] = SimpleNamespace(x=0.75, y=0.5)
        self.assertEqual(landmarks_to_normalized(landmarks, EYE_CORNERS, mirror=False), (0.0, 0.0))
        self.assertEqual(landmarks_to_normalized(landmarks, IRIS_CENTERS, mirror=False), (0.5, 0.0))


class SampleFreshnessTests(unittest.TestCase):
    def test_no_sample_yet_is_not_found(self):
        self.assertEqual(evaluate_sample(None, 10.0, 0.15), (False, None, None))

    def test_fresh_face_is_found(self):
        self.assertEqual(evaluate_sample((0.2, -0.1, 9.9, True), 10.0, 0.15), (True, 0.2, -0.1))

    def test_frame_without_face_is_not_found(self):
        self.assertEqual(evaluate_sample((0.0, 0.0, 9.95, False), 10.0, 0.15), (False, None, None))

    def test_stale_sample_is_not_found(self):
        # Camera froze 0.5 s ago: must count as lost, not as a valid position.
        self.assertEqual(evaluate_sample((0.2, -0.1, 9.5, True), 10.0, 0.15), (False, None, None))


class TrackingGainTests(unittest.TestCase):
    def test_default_gain_keeps_old_behaviour(self):
        self.assertEqual(TrackingInput().update(0.4, -0.2, True, 0.02), (0.4, -0.2))

    def test_gain_is_applied_after_calibration(self):
        tracking = TrackingInput(gain=2.5)
        tracking.calibrate(0.4, 0.0)  # viewer sits off-centre in the image
        x, y = tracking.update(0.5, 0.1, True, 0.02)
        self.assertAlmostEqual(x, 0.25)
        self.assertAlmostEqual(y, 0.25)

    def test_gain_output_is_clamped(self):
        tracking = TrackingInput(gain=2.5)
        self.assertEqual(tracking.update(0.8, -0.8, True, 0.02), (1.0, -1.0))


if __name__ == "__main__":
    unittest.main()
