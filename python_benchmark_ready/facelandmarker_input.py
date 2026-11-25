"""Webcam + MediaPipe Face Landmarker adapter for the parallax prototype.

Turns Face Landmarker output into the same interface the mouse, scripted and
simulated modes use: a NormalizedInput sample in [-1, 1] plus a
tracking_found flag.

The camera and the detector run in a background thread, so the 60 FPS render
loop never waits for the 30 FPS webcam. The render loop only reads the latest
result. A result older than max_age_seconds counts as lost tracking, so a
frozen camera or a crashed thread makes the scene hold and then return to
center instead of freezing on an old position.

cv2 and mediapipe are imported only when the provider is created, so the other
input modes (and the unit tests) run without them installed.
"""

import os
import threading
import time
import urllib.request

from normalized_input import NormalizedInput
from one_euro_filter import OneEuroFilter

MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/face_landmarker/"
             "face_landmarker/float16/1/face_landmarker.task")
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "face_landmarker.task")

# Face Landmarker landmark indices.
EYE_CORNERS = (33, 133, 362, 263)  # outer/inner corner of each eye: follows the head only
IRIS_CENTERS = (468, 473)          # iris centres: also move when the viewer looks around
TRACK_POINTS = {"eyes": EYE_CORNERS, "iris": IRIS_CENTERS}


def landmarks_to_normalized(landmarks, ids=EYE_CORNERS, mirror=True):
    """Average the chosen landmarks and convert them to the parallax range.

    MediaPipe gives x/y from 0 to 1 across the camera image. The parallax code
    wants -1 (left/top) to +1 (right/bottom), with 0 at the image centre.

    The webcam image is not mirrored: when the viewer moves to their right,
    they move left in the image. mirror=True flips x so that moving right
    gives a positive x, the same as moving the mouse right.
    """
    x = sum(landmarks[i].x for i in ids) / len(ids)
    y = sum(landmarks[i].y for i in ids) / len(ids)
    nx = (x - 0.5) * 2.0
    ny = (y - 0.5) * 2.0
    return (-nx if mirror else nx), ny


def evaluate_sample(sample, now, max_age_seconds):
    """Decide whether the latest tracker result can be used this frame.

    sample is None or (x, y, captured_at, face_found).
    Returns (tracking_found, x, y).
    """
    if sample is None:
        return False, None, None
    x, y, captured_at, face_found = sample
    if not face_found or now - captured_at > max_age_seconds:
        return False, None, None
    return True, x, y


class FaceLandmarkerInputProvider:
    """Background webcam tracker that writes into a NormalizedInput."""

    def __init__(self, camera_index=0, point="eyes", mirror=True,
                 max_age_seconds=0.15, width=640, height=480,
                 filter_enabled=True, min_cutoff=1.0,
                 beta=0.5, d_cutoff=1.0):
        import cv2
        import mediapipe as mp
        from mediapipe.tasks import python as mp_tasks
        from mediapipe.tasks.python import vision

        self._cv2 = cv2
        self._mp = mp
        self.ids = TRACK_POINTS[point]
        self.mirror = mirror
        self.max_age_seconds = max_age_seconds
        self.filter_enabled = filter_enabled

        self.filter_x = OneEuroFilter(
            min_cutoff=min_cutoff,
            beta=beta,
            d_cutoff=d_cutoff
        )

        self.filter_y = OneEuroFilter(
            min_cutoff=min_cutoff,
            beta=beta,
            d_cutoff=d_cutoff
)
        if not os.path.exists(MODEL_PATH):
            print("Downloading Face Landmarker model...")
            urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)

        self._cap = cv2.VideoCapture(camera_index)
        if not self._cap.isOpened():
            raise RuntimeError(f"Could not open camera {camera_index}")
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        options = vision.FaceLandmarkerOptions(
            base_options=mp_tasks.BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1,
        )
        self._landmarker = vision.FaceLandmarker.create_from_options(options)

        self._lock = threading.Lock()
        self._latest = None          # (x, y, captured_at, face_found)
        self.detector_ms = 0.0       # time spent in detect_for_video, last frame
        self.camera_fps = 0.0        # rate at which the thread gets new frames
        self.error = None            # set if the thread stops because of an exception
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        cv2, mp = self._cv2, self._mp
        start = time.monotonic()
        last_ts = -1
        last_frame_time = None
        try:
            while self._running:
                ok, frame = self._cap.read()
                if not ok:
                    time.sleep(0.005)
                    continue
                captured_at = time.perf_counter()

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                # VIDEO mode needs strictly increasing timestamps in ms.
                ts = max(int((time.monotonic() - start) * 1000), last_ts + 1)
                last_ts = ts
                result = self._landmarker.detect_for_video(image, ts)
                detected_at = time.perf_counter()

                if result.face_landmarks:
                    x, y = landmarks_to_normalized(result.face_landmarks[0], self.ids, self.mirror)

                    if self.filter_enabled:
                        x = self.filter_x.filter(x, captured_at)
                        y = self.filter_y.filter(y, captured_at)
                    sample = (x, y, captured_at, True)
                else:
                    self.filter_x.reset()
                    self.filter_y.reset()

                    sample = (0.0, 0.0, captured_at, False)
                with self._lock:
                    self._latest = sample
                    self.detector_ms = (detected_at - captured_at) * 1000.0
                    if last_frame_time is not None and captured_at > last_frame_time:
                        self.camera_fps = 1.0 / (captured_at - last_frame_time)
                last_frame_time = captured_at
        except Exception as exc:  # keep the renderer alive; update() reports lost tracking
            self.error = exc
            print(f"Face Landmarker thread stopped: {exc!r}")

    def update(self, input_state: NormalizedInput) -> bool:
        """Write the latest valid sample into input_state.

        Returns tracking_found. When it is False, input_state is left unchanged
        and TrackingInput handles holding / returning to centre.
        """
        with self._lock:
            sample = self._latest
        found, x, y = evaluate_sample(sample, time.perf_counter(), self.max_age_seconds)
        if found:
            input_state.set_position(x, y)
        return found

    def close(self):
        self._running = False
        self._thread.join(timeout=1.0)
        self._cap.release()
        self._landmarker.close()
