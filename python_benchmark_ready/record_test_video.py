"""Record one reusable test clip from the webcam (local file only)."""
import argparse
from pathlib import Path
import time
import cv2

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("output", type=Path)
p.add_argument("--camera", type=int, default=0)
p.add_argument("--seconds", type=float, default=30)
p.add_argument("--empty", action="store_true", help="Record a no-face negative control")
a = p.parse_args()
if a.seconds <= 0 or a.output.exists():
    p.error("Use a positive duration and a new output path")
cap = cv2.VideoCapture(a.camera)
writer = None
try:
    if not cap.isOpened():
        raise RuntimeError("Cannot open webcam")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    print("Keep your face out of frame." if a.empty else "Keep your face centered for the first 5 seconds, then move slowly left/right/up/down. Keep your face visible.", flush=True)
    frames = 0
    start = time.perf_counter()
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not (0 < fps <= 120):
        fps = 30
    while time.perf_counter() - start < a.seconds:
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError("Camera frame read failed")
        if writer is None:
            h, w = frame.shape[:2]
            writer = cv2.VideoWriter(str(a.output), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
            if not writer.isOpened():
                raise RuntimeError("Cannot write video; use an .mp4 filename")
        writer.write(frame)
        frames += 1
        cv2.imshow("Record test input (Esc cancels)", frame)
        if cv2.waitKey(1) & 0xff == 27:
            raise RuntimeError("Recording cancelled; remove the partial video before retrying")
    print(f"Saved {frames} frames to {a.output}; encoded FPS {fps:.2f}")
finally:
    cap.release()
    if writer:
        writer.release()
    cv2.destroyAllWindows()
