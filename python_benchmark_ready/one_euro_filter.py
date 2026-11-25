import math


class OneEuroFilter:

    def __init__(self, min_cutoff=1.0, beta=0.5, d_cutoff=1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.reset()

    def reset(self):
        self.previous_raw = None
        self.previous_value = None
        self.previous_derivative = 0.0
        self.previous_time = None

    def alpha(self, cutoff, dt):
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return dt / (dt + tau)

    def filter(self, value, timestamp):

        if self.previous_time is None:
            self.previous_time = timestamp
            self.previous_raw = value
            self.previous_value = value
            return value

        dt = timestamp - self.previous_time

        if dt <= 0:
            return self.previous_value

        derivative = (value - self.previous_raw) / dt

        alpha_d = self.alpha(self.d_cutoff, dt)

        smooth_derivative = (
                alpha_d * derivative
                + (1.0 - alpha_d) * self.previous_derivative
        )

        cutoff = (
                self.min_cutoff
                + self.beta * abs(smooth_derivative)
        )

        alpha_x = self.alpha(cutoff, dt)

        filtered_value = (
                alpha_x * value
                + (1.0 - alpha_x) * self.previous_value
        )

        self.previous_raw = value
        self.previous_value = filtered_value
        self.previous_derivative = smooth_derivative
        self.previous_time = timestamp

        return filtered_value