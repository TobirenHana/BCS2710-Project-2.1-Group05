"""Optional CSV output for per-frame prototype timings."""

import atexit
import csv
from datetime import datetime


class BenchmarkLogger:
    def __init__(self, path: str, input_mode: str):
        self.path = path or datetime.now().strftime("benchmark_%Y%m%d_%H%M%S_%f.csv")
        # Refuse to overwrite an earlier benchmark.
        self._file = open(self.path, "x", newline="", encoding="utf-8")
        atexit.register(self.close)
        self._writer = csv.writer(self._file)
        self._writer.writerow(
            ("frame_index", "input_mode", "frame_time_ms", "fps", "input_to_render_ms")
        )
        self._input_mode = input_mode
        self._frame = 0

    def log_frame(self, frame_seconds: float, input_to_render_seconds: float) -> None:
        self._writer.writerow((
            self._frame,
            self._input_mode,
            frame_seconds * 1000.0,
            1.0 / frame_seconds if frame_seconds > 0.0 else 0.0,
            input_to_render_seconds * 1000.0,
        ))
        self._frame += 1

    def close(self) -> None:
        self._file.close()
