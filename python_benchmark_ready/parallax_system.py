import pygame
import json
import time
import math
import argparse
from pathlib import Path
from normalized_input import NormalizedInput
from scripted_input import ScriptedInputProvider
from simulated_input import SimulatedInputProvider
from tracking_input import TrackingInput
from benchmark import BenchmarkLogger


def update_mouse_input(input_state: NormalizedInput, width: int, height: int) -> None:
    mouse_x, mouse_y = pygame.mouse.get_pos()
    input_state.set_position(
        (mouse_x - width // 2) / (width / 2),
        (mouse_y - height // 2) / (height / 2),
    )

parser = argparse.ArgumentParser(description="2.5D parallax prototype")
parser.add_argument("--input-mode", choices=("mouse", "scripted", "simulated", "tracker"), default="mouse")
parser.add_argument("--camera", type=int, default=0, help="Webcam index for --input-mode tracker")
parser.add_argument("--video", help="Replay a recorded video instead of webcam in tracker mode")
parser.add_argument("--track-point", choices=("eyes", "iris"), default="eyes",
    help="Tracked point: eye-corner midpoint (head only) or iris midpoint")
parser.add_argument(
    "--benchmark", nargs="?", const="", default=None, metavar="CSV_PATH",
    help="Log per-frame timings to CSV (default: a unique benchmark_*.csv file).",
)
parser.add_argument("--test", choices=("basic", "complexity", "parallax", "stability"), default="basic")
parser.add_argument("--objects", type=int, choices=(3, 5, 20, 50), default=3)
parser.add_argument("--parallax", choices=("on", "off"), default="on")
parser.add_argument("--duration", type=float, default=60.0, help="Seconds of recorded data")
parser.add_argument("--warmup", type=float, default=5.0)
parser.add_argument("--fps-cap", type=int, choices=(0, 60), default=None, help="0 = uncapped; default uses config")
parser.add_argument("--run", type=int, default=1)
args = parser.parse_args()
if args.video and args.input_mode != "tracker":
    parser.error("--video requires --input-mode tracker")
if args.duration <= 0 or args.warmup < 0:
    parser.error("Duration must be positive and warmup cannot be negative")
scripted_input = ScriptedInputProvider() if args.input_mode == "scripted" else None
simulated_input = SimulatedInputProvider() if args.input_mode == "simulated" else None
benchmark = BenchmarkLogger(args.benchmark, args.input_mode, test=args.test,
    object_count=args.objects, parallax_enabled=args.parallax == "on", run=args.run) if args.benchmark is not None else None

try:
    with open("config.json", "r") as f:
        config = json.load(f)
except Exception:
    config = {
        "width": 800,
        "height": 600,
        "fps": 60,
        "far_factor": -0.04,
        "mid_factor": -0.28,
        "near_factor": -0.70
    }

# The tracker is created before the window so a missing camera fails fast.
tracker_input = None
if args.input_mode == "tracker":
    from facelandmarker_input import FaceLandmarkerInputProvider
    tracker_input = FaceLandmarkerInputProvider(
        camera_index=args.camera,
        video_path=args.video,
        telemetry=benchmark is not None,
        point=args.track_point,
        mirror=config.get("tracking_mirror", True),
        max_age_seconds=config.get("tracking_max_age_seconds", 0.15),
        width=config.get("tracking_camera_width", 640),
        height=config.get("tracking_camera_height", 480),
        filter_enabled=config.get("tracking_filter_enabled", True),
        min_cutoff=config.get("tracking_filter_min_cutoff", 1.0),
        beta=config.get("tracking_filter_beta", 0.5),
        d_cutoff=config.get("tracking_filter_d_cutoff", 1.0),
    )

pygame.init()
WIDTH = config.get("width", 800)
HEIGHT = config.get("height", 600)
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("2.5D Parallax - Rounded Box Perspective Shadows")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 15)

center_x = WIDTH // 2
center_y = HEIGHT // 2

eye_x, eye_y = 0.0, 0.0
raw_input = NormalizedInput()
input_state = NormalizedInput()
# Gain only applies to the webcam tracker; mouse/scripted/simulated already span [-1, 1].
tracking_gain = config.get("tracking_gain", 2.5) if tracker_input is not None else 1.0
tracking = TrackingInput(config.get("tracking_hold_seconds", 0.5), gain=tracking_gain)
tracking_found = True
auto_calibrated = tracker_input is None or not config.get("tracking_auto_calibrate", False)
calibration_samples = []
calibration_sample_count = max(1, int(config.get("tracking_calibration_samples", 30)))
last_calibration_timestamp = None
running = True
experiment_started = time.perf_counter()
recording_started = None

BALL_RADIUS = 45
BALL_SH_PAD = 16
BALL_SH_DIM = (BALL_RADIUS + BALL_SH_PAD) * 2
ball_base_shadow = pygame.Surface((BALL_SH_DIM, BALL_SH_DIM), pygame.SRCALPHA)
for r in range(BALL_RADIUS + BALL_SH_PAD, BALL_RADIUS - 6, -2):
    factor = 1.0 - (r - BALL_RADIUS + 6) / (BALL_SH_PAD + 12)
    alpha = int(115 * max(0.0, min(1.0, factor**1.5)))
    pygame.draw.circle(ball_base_shadow, (4, 6, 12, alpha), (BALL_SH_DIM // 2, BALL_SH_DIM // 2), r)

ball_ambient_surf = pygame.Surface((BALL_RADIUS * 2, BALL_RADIUS * 2), pygame.SRCALPHA)
for r in range(BALL_RADIUS, 4, -2):
    alpha = int(28 * (1.0 - r / BALL_RADIUS))
    pygame.draw.circle(ball_ambient_surf, (255, 255, 255, alpha), (BALL_RADIUS - 8, BALL_RADIUS - 8), r)

def get_rounded_rect_vertices(rect, radius, points_per_corner=6):
    rx, ry, rw, rh = rect
    r = min(radius, rw // 2, rh // 2)
    vertices = []

    corners = [
        (rx + rw - r, ry + r, 0.0, math.pi * 0.5),           
        (rx + rw - r, ry + rh - r, math.pi * 0.5, math.pi),   
        (rx + r, ry + rh - r, math.pi, math.pi * 1.5),        
        (rx + r, ry + r, math.pi * 1.5, math.pi * 2.0)       
    ]

    for cx, cy, start_angle, end_angle in corners:
        for i in range(points_per_corner):
            theta = start_angle + (end_angle - start_angle) * (i / (points_per_corner - 1))
            px = cx + r * math.sin(theta)
            py = cy - r * math.cos(theta)
            vertices.append((px, py))

    return vertices

def render_rounded_perspective_shadow(dest_surface, rect, corner_radius, light_pos, height_ratio, base_alpha):
    lx, ly = light_pos
    orig_vertices = get_rounded_rect_vertices(rect, corner_radius)
    n = len(orig_vertices)

    def calc_projection(scale_mod):
        proj = []
        for vx, vy in orig_vertices:
            px = vx + (vx - lx) * (height_ratio * scale_mod)
            py = vy + (vy - ly) * (height_ratio * scale_mod)
            proj.append((px, py))
        return proj

    temp_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

    
    penumbra_proj = calc_projection(1.18)
    pygame.draw.polygon(temp_surf, (5, 8, 14, int(base_alpha * 0.35)), penumbra_proj)

    
    umbra_proj = calc_projection(1.0)
    pygame.draw.polygon(temp_surf, (3, 4, 8, int(base_alpha * 0.85)), umbra_proj)

    
    for i in range(n):
        next_i = (i + 1) % n
        p1 = orig_vertices[i]
        p2 = orig_vertices[next_i]
        edge_mid_x = (p1[0] + p2[0]) * 0.5
        edge_mid_y = (p1[1] + p2[1]) * 0.5
        
        edge_dx = p2[0] - p1[0]
        edge_dy = p2[1] - p1[1]
        normal_x = -edge_dy
        normal_y = edge_dx
        light_dir_x = edge_mid_x - lx
        light_dir_y = edge_mid_y - ly

        if (light_dir_x * normal_x + light_dir_y * normal_y) > 0:
            quad = [p1, p2, umbra_proj[next_i], umbra_proj[i]]
            pygame.draw.polygon(temp_surf, (4, 5, 10, int(base_alpha * 0.55)), quad)

    dest_surface.blit(temp_surf, (0, 0))

previous_frame_time = time.perf_counter()
while running:
    start_time = time.perf_counter()
    dt = start_time - previous_frame_time
    previous_frame_time = start_time
    calibrate_requested = False

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_c:
                calibrate_requested = True
            elif event.key == pygame.K_x:
                tracking.reset()
            elif simulated_input is not None:
                if event.key == pygame.K_SPACE:
                    simulated_input.toggle_pause()
                elif event.key == pygame.K_l:
                    tracking_found = not tracking_found
                elif event.key == pygame.K_r:
                    simulated_input.reset()
                    tracking.reset()
                    tracking_found = True

    if tracker_input is not None:
        tracking_found = tracker_input.update(raw_input)
    elif simulated_input is not None:
        simulated_input.update(raw_input)
    elif scripted_input is not None:
        scripted_input.update(raw_input)
    else:
        update_mouse_input(raw_input, WIDTH, HEIGHT)
    input_start = time.perf_counter() if benchmark is not None else None
    raw_x, raw_y = raw_input.get_position()
    if tracking_found and calibrate_requested:
        tracking.calibrate(raw_x, raw_y)
        auto_calibrated = True
        calibration_samples.clear()

    elif not auto_calibrated:
        if not tracking_found:
            calibration_samples.clear()
            last_calibration_timestamp = None

        elif tracker_input.sample_timestamp != last_calibration_timestamp:
            last_calibration_timestamp = tracker_input.sample_timestamp
            calibration_samples.append((raw_x, raw_y))

            if len(calibration_samples) >= calibration_sample_count:
                center_x_avg = sum(p[0] for p in calibration_samples) / len(calibration_samples)
                center_y_avg = sum(p[1] for p in calibration_samples) / len(calibration_samples)

                tracking.calibrate(center_x_avg, center_y_avg)
                auto_calibrated = True
                calibration_samples.clear()
    x, y = tracking.update(raw_x, raw_y, tracking_found, dt)
    input_state.set_position(x, y)
    target_x, target_y = input_state.get_position()

    # Keep lighting unsmoothed, as it was with the original mouse input.
    light_x = center_x + target_x * (WIDTH / 2)
    light_y = center_y + target_y * (HEIGHT / 2)

    if args.parallax == "off":
        target_x, target_y = 0.0, 0.0
    eye_x += 0.2 * (target_x - eye_x)
    eye_y += 0.2 * (target_y - eye_y)

    screen.fill((26, 29, 41))

    max_offset_x = WIDTH * 0.22
    max_offset_y = HEIGHT * 0.22

    FAR_W, FAR_H = 480, 330
    far_dx = int(eye_x * config.get("far_factor", -0.04) * max_offset_x)
    far_dy = int(eye_y * config.get("far_factor", -0.04) * max_offset_y)
    far_rect = (center_x + far_dx - FAR_W // 2, center_y + far_dy - FAR_H // 2, FAR_W, FAR_H)

    render_rounded_perspective_shadow(screen, far_rect, corner_radius=12, light_pos=(light_x, light_y), height_ratio=0.025, base_alpha=80)
    pygame.draw.rect(screen, (46, 54, 74), pygame.Rect(far_rect), border_radius=12)

    MID_W, MID_H = 290, 195
    mid_dx = int(eye_x * config.get("mid_factor", -0.28) * max_offset_x)
    mid_dy = int(eye_y * config.get("mid_factor", -0.28) * max_offset_y)
    mid_rect = (center_x + mid_dx - MID_W // 2, center_y + mid_dy - MID_H // 2, MID_W, MID_H)

    render_rounded_perspective_shadow(screen, mid_rect, corner_radius=10, light_pos=(light_x, light_y), height_ratio=0.075, base_alpha=120)
    pygame.draw.rect(screen, (74, 102, 146), pygame.Rect(mid_rect), border_radius=10)
    pygame.draw.rect(screen, (98, 128, 178), pygame.Rect(mid_rect), width=1, border_radius=10)

    near_dx = int(eye_x * config.get("near_factor", -0.70) * max_offset_x)
    near_dy = int(eye_y * config.get("near_factor", -0.70) * max_offset_y)
    ball_x = center_x + near_dx
    ball_y = center_y + near_dy

    dx_ball = ball_x - light_x
    dy_ball = ball_y - light_y
    dist_ball = math.hypot(dx_ball, dy_ball)

    stretch = 1.0 + min(dist_ball / 900.0, 0.25)
    sw = int(BALL_SH_DIM * stretch)
    sh = int(BALL_SH_DIM)
    scaled_ball_shadow = pygame.transform.smoothscale(ball_base_shadow, (sw, sh))

    if dist_ball > 1.5:
        angle = -math.degrees(math.atan2(dy_ball, dx_ball))
        rot_ball_shadow = pygame.transform.rotate(scaled_ball_shadow, angle)
    else:
        rot_ball_shadow = scaled_ball_shadow

    sh_x = int(dx_ball * 0.10)
    sh_y = int(dy_ball * 0.10)
    sh_rect = rot_ball_shadow.get_rect(center=(ball_x + sh_x, ball_y + sh_y))
    screen.blit(rot_ball_shadow, sh_rect.topleft)

    pygame.draw.circle(screen, (242, 186, 52), (ball_x, ball_y), BALL_RADIUS)
    screen.blit(ball_ambient_surf, (ball_x - BALL_RADIUS, ball_y - BALL_RADIUS))
    # Extra comparable primitives to increase scene complexity.
    # The original scene already contains three main visual objects.
    for obj_idx in range(args.objects - 3):
        col = obj_idx % 10
        row = obj_idx // 10
        depth = (obj_idx % 3 + 1) / 3.0
        shift_x = int(eye_x * depth * WIDTH * 0.10)
        shift_y = int(eye_y * depth * HEIGHT * 0.10)
        x = int(WIDTH * 0.12 + col * WIDTH * 0.075 + shift_x)
        y = int(HEIGHT * 0.15 + row * HEIGHT * 0.10 + shift_y)
        pygame.draw.circle(screen, (135, 165, 204), (x, y), 10)
    input_to_render_seconds = time.perf_counter() - input_start if benchmark is not None else None

    clock.tick(args.fps_cap if args.fps_cap is not None else config.get("fps", 60))
    latency_ms = (time.perf_counter() - start_time) * 1000
    fps = clock.get_fps()

    screen.blit(font.render(f"FPS: {fps:.1f}", True, (210, 215, 220)), (25, 20))
    screen.blit(font.render(f"Loop Time: {latency_ms:.2f} ms", True, (210, 215, 220)), (25, 40))
    screen.blit(font.render(f"Eye Norm: ({eye_x:.2f}, {eye_y:.2f})", True, (210, 215, 220)), (25, 60))
    tracking_text = f"Input: {tracking.status} | Center: ({tracking.center_x:+.2f}, {tracking.center_y:+.2f})"
    screen.blit(font.render(tracking_text, True, (210, 215, 220)), (25, 80))
    screen.blit(font.render("C: set center | X: clear center", True, (210, 215, 220)), (25, 100))

    if tracker_input is not None:
        tracker_text = (f"Tracker: {'face found' if tracking_found else 'no face'} | "
                        f"detector {tracker_input.detector_ms:.1f} ms | camera {tracker_input.camera_fps:.0f} FPS | "
                        f"gain {tracking.gain:.1f}")
        if tracker_input.error is not None:
            tracker_text = f"Tracker stopped: {tracker_input.error!r}"
        screen.blit(font.render(tracker_text, True, (210, 215, 220)), (25, 120))
    if tracker_input is not None:
        if not auto_calibrated:
                message = (
                    f"Calibrating: {len(calibration_samples)}/"
                    f"{calibration_sample_count} - Keep your head still"
                )
                color = (255, 200, 50)
        else:
                message = "Calibration complete"
                color = (100, 220, 140)

        screen.blit(font.render(message, True, color), (25, 140))
    if simulated_input is not None:
        status = "PAUSED" if simulated_input.paused else "PLAYING"
        raw_text = f"Raw x={raw_x:+.2f}, y={raw_y:+.2f}" if tracking_found else "Raw position unavailable"
        demo_lines = (
            "SIMULATED INPUT - NO WEBCAM TRACKING",
            f"{status} | {simulated_input.stage} | {raw_text}",
            f"Output x={target_x:+.2f}, y={target_y:+.2f} | {tracking.status}",
            "C: set center | X: clear center | L: lose/restore tracking",
            "Space: pause/resume | R: restart | Esc: quit",
        )
        for index, line in enumerate(demo_lines):
            screen.blit(font.render(line, True, (210, 215, 220)), (25, HEIGHT - 110 + index * 20))

    pygame.display.flip()
    if benchmark is not None:
        current = time.perf_counter()
        if current - experiment_started >= args.warmup:
            if recording_started is None:
                recording_started = current
            frame_seconds = current - start_time
            metrics = ()
            if tracker_input is not None:
                stamp = tracker_input.sample_timestamp
                metrics = (int(tracking_found), tracker_input.sample_age_ms if tracking_found else "",
                           (current - stamp) * 1000 if stamp is not None else "", int(auto_calibrated),
                           raw_x if tracking_found else "", raw_y if tracking_found else "",
                           target_x, target_y, tracking.status)
            benchmark.log_frame(frame_seconds, input_to_render_seconds, metrics)
            if current - recording_started >= args.duration:
                running = False

pygame.quit()
if tracker_input is not None:
    tracker_input.close()
    if benchmark is not None and recording_started is not None:
        tracker_input.save_telemetry(str(Path(benchmark.path).with_suffix(".tracking.csv")),
                                     recording_started, current)
    if tracker_input.error is not None:
        raise RuntimeError("Tracker failed") from tracker_input.error
if benchmark is not None:
    benchmark.close()
    print(f"Benchmark saved to {benchmark.path}")
