"""Center calibration and tracking-loss handling, without a camera dependency."""


class TrackingInput:
    def __init__(self, hold_seconds=0.5):
        self.hold_seconds = hold_seconds
        self.reset()

    def reset(self):
        self.center_x = 0.0
        self.center_y = 0.0
        self.x = 0.0
        self.y = 0.0
        self.lost_seconds = 0.0
        self.recovering = False
        self.status = "Tracking"

    def calibrate(self, x, y):
        # Remember the current raw position as the new center.
        self.center_x = x
        self.center_y = y
        self.x = 0.0
        self.y = 0.0

    def update(self, x, y, tracking_found, dt):
        # dt is the elapsed time in seconds since the previous frame.
        dt = max(0.0, dt)

        if tracking_found:
            target_x = max(-1.0, min(1.0, x - self.center_x))
            target_y = max(-1.0, min(1.0, y - self.center_y))

            if self.lost_seconds > 0.0:
                self.recovering = True
            self.lost_seconds = 0.0

            if self.recovering:
                # Ease back to the live position instead of jumping to it.
                amount = min(dt * 8.0, 1.0)
                self.x += (target_x - self.x) * amount
                self.y += (target_y - self.y) * amount
                self.status = "Recovering"
                if abs(target_x - self.x) < 0.001 and abs(target_y - self.y) < 0.001:
                    self.recovering = False
                    self.x = target_x
                    self.y = target_y
                    self.status = "Tracking"
            else:
                self.x = target_x
                self.y = target_y
                self.status = "Tracking"
        else:
            self.lost_seconds += dt
            if self.lost_seconds <= self.hold_seconds:
                self.status = "Holding last position"
            else:
                # After the short hold, move gradually toward the center.
                return_dt = min(dt, self.lost_seconds - self.hold_seconds)
                amount = min(return_dt * 3.0, 1.0)
                self.x += (0.0 - self.x) * amount
                self.y += (0.0 - self.y) * amount
                if abs(self.x) < 0.001 and abs(self.y) < 0.001:
                    self.x = 0.0
                    self.y = 0.0
                self.status = "Returning to center"

        return self.x, self.y
