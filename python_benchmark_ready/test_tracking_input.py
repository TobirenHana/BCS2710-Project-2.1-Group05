import unittest

from tracking_input import TrackingInput


class TrackingInputTests(unittest.TestCase):
    def test_normal_input_is_unchanged(self):
        tracking = TrackingInput()
        self.assertEqual(tracking.update(0.4, -0.2, True, 0.02), (0.4, -0.2))

    def test_calibration_subtracts_center_and_clamps(self):
        tracking = TrackingInput()
        tracking.calibrate(0.4, -0.2)
        self.assertEqual(tracking.update(0.4, -0.2, True, 0.02), (0.0, 0.0))
        x, y = tracking.update(0.6, 0.1, True, 0.02)
        self.assertAlmostEqual(x, 0.2)
        self.assertAlmostEqual(y, 0.3)
        self.assertEqual(tracking.update(-1.0, 1.0, True, 0.02), (-1.0, 1.0))

    def test_short_loss_holds_last_position_and_ignores_invalid_sample(self):
        tracking = TrackingInput()
        tracking.update(0.8, -0.4, True, 0.02)
        self.assertEqual(tracking.update(None, None, False, 0.25), (0.8, -0.4))
        self.assertEqual(tracking.update(None, None, False, 0.25), (0.8, -0.4))
        self.assertEqual(tracking.status, "Holding last position")

    def test_long_loss_returns_to_center(self):
        tracking = TrackingInput()
        tracking.update(0.8, -0.4, True, 0.02)
        tracking.update(None, None, False, 0.5)
        x, y = tracking.update(None, None, False, 0.02)
        self.assertTrue(0.0 < x < 0.8)
        self.assertTrue(-0.4 < y < 0.0)
        for _ in range(300):
            x, y = tracking.update(None, None, False, 0.02)
        self.assertEqual((x, y), (0.0, 0.0))

    def test_only_time_after_hold_is_used_for_return(self):
        tracking = TrackingInput(hold_seconds=0.1)
        tracking.update(1.0, 0.0, True, 0.02)
        x, y = tracking.update(None, None, False, 0.15)
        self.assertAlmostEqual(x, 0.85)
        self.assertEqual(y, 0.0)

    def test_recovery_is_gradual_and_keeps_calibration(self):
        tracking = TrackingInput()
        tracking.calibrate(0.2, 0.0)
        tracking.update(0.2, 0.0, True, 0.02)
        tracking.update(None, None, False, 1.0)
        x, y = tracking.update(0.8, 0.0, True, 0.02)
        self.assertTrue(0.0 < x < 0.6)
        self.assertEqual(tracking.status, "Recovering")
        for _ in range(100):
            x, y = tracking.update(0.8, 0.0, True, 0.02)
        self.assertAlmostEqual(x, 0.6)
        self.assertEqual(tracking.status, "Tracking")
        self.assertEqual(tracking.center_x, 0.2)

    def test_startup_without_tracking_stays_centered(self):
        tracking = TrackingInput()
        self.assertEqual(tracking.update(None, None, False, 0.1), (0.0, 0.0))
        self.assertEqual(tracking.update(None, None, False, 1.0), (0.0, 0.0))

    def test_reset_clears_calibration_and_loss(self):
        tracking = TrackingInput()
        tracking.calibrate(0.4, 0.2)
        tracking.update(None, None, False, 1.0)
        tracking.reset()
        self.assertEqual(tracking.update(0.4, 0.2, True, 0.02), (0.4, 0.2))
        self.assertEqual(tracking.center_x, 0.0)
        self.assertEqual(tracking.lost_seconds, 0.0)


if __name__ == "__main__":
    unittest.main()
