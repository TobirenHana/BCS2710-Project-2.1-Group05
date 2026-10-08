"""CSV benchmark logger for the Pygame parallax prototype."""
import atexit
import csv
import os
import time
from datetime import datetime

try:
    import psutil
except ImportError:
    psutil = None


class BenchmarkLogger:
    def __init__(self, path, input_mode, test="basic", object_count=3,
                 parallax_enabled=True, run=1):
        self.path = path or datetime.now().strftime("benchmark_%Y%m%d_%H%M%S_%f.csv")
        self._file = open(self.path, "x", newline="", encoding="utf-8")
        atexit.register(self.close)
        self._writer = csv.writer(self._file)
        self._writer.writerow((
            "frame_index", "elapsed_s", "test", "run", "input_mode", "object_count",
            "parallax_enabled", "frame_time_ms", "fps", "input_to_render_ms",
            "cpu_percent", "memory_mb"
        ))
        self.input_mode = input_mode
        self.test = test
        self.object_count = object_count
        self.parallax_enabled = parallax_enabled
        self.run = run
        self._frame = 0
        self._start = None
        self._process = psutil.Process(os.getpid()) if psutil else None
        self._cpu = ""
        self._memory = ""
        self._last_sample = -1.0
        if self._process:
            self._process.cpu_percent(interval=None)

    def log_frame(self, frame_seconds, input_to_render_seconds):
        now = time.perf_counter()
        if self._start is None:
            self._start = now
        elapsed = now - self._start
        if self._process and (self._last_sample < 0 or elapsed - self._last_sample >= 1.0):
            self._cpu = self._process.cpu_percent(interval=None)
            self._memory = round(self._process.memory_info().rss / (1024 * 1024), 2)
            self._last_sample = elapsed
        self._writer.writerow((
            self._frame, round(elapsed, 4), self.test, self.run,
            self.input_mode, self.object_count, int(self.parallax_enabled),
            round(frame_seconds * 1000.0, 4),
            round(1.0 / frame_seconds, 4) if frame_seconds > 0 else 0.0,
            round(input_to_render_seconds * 1000.0, 4),
            self._cpu, self._memory
        ))
        self._frame += 1

    def close(self):
        if not self._file.closed:
            self._file.close()
