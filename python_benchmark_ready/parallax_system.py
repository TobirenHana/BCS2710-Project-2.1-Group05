import pygame
import json
import time
import math
import argparse
from normalized_input import NormalizedInput
from scripted_input import ScriptedInputProvider
from benchmark import BenchmarkLogger


def update_mouse_input(input_state: NormalizedInput, width: int, height: int) -> None:
    """Debug adapter: convert mouse pixels to the shared normalized interface."""
    mouse_x, mouse_y = pygame.mouse.get_pos()
    input_state.set_position(
        (mouse_x - width // 2) / (width / 2),
        (mouse_y - height // 2) / (height / 2),
    )

parser = argparse.ArgumentParser(description="2.5D parallax prototype")
parser.add_argument("--input-mode", choices=("mouse", "scripted"), default="mouse")
parser.add_argument(
    "--benchmark", nargs="?", const="", default=None, metavar="CSV_PATH",
    help="Log per-frame timings to CSV (default: a unique benchmark_*.csv file).",
)
parser.add_argument("--test", choices=("basic", "complexity", "parallax", "stability"), default="basic")
parser.add_argument("--objects", type=int, choices=(3, 5, 20, 50), default=3)
parser.add_argument("--parallax", choices=("on", "off"), default="on")
parser.add_argument("--duration", type=float, default=60.0, help="Seconds of recorded data")
parser.add_argument("--warmup", type=float, default=5.0)
parser.add_argument("--run", type=int, default=1)
args = parser.parse_args()
if args.duration <= 0 or args.warmup < 0:
    parser.error("Duration must be positive and warmup cannot be negative")
scripted_input = ScriptedInputProvider() if args.input_mode == "scripted" else None
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
input_state = NormalizedInput()
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

while running:
    start_time = time.perf_counter()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            running = False

    # Replace this input selection with input_state.set_position(x, y) for tracking.
    if scripted_input is not None:
        scripted_input.update(input_state)
    else:
        update_mouse_input(input_state, WIDTH, HEIGHT)
    input_start = time.perf_counter() if benchmark is not None else None
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

    clock.tick(config.get("fps", 60))
    latency_ms = (time.perf_counter() - start_time) * 1000
    fps = clock.get_fps()

    screen.blit(font.render(f"FPS: {fps:.1f}", True, (210, 215, 220)), (25, 20))
    screen.blit(font.render(f"Loop Time: {latency_ms:.2f} ms", True, (210, 215, 220)), (25, 40))
    screen.blit(font.render(f"Eye Norm: ({eye_x:.2f}, {eye_y:.2f})", True, (210, 215, 220)), (25, 60))

    pygame.display.flip()
    if benchmark is not None:
        current = time.perf_counter()
        if current - experiment_started >= args.warmup:
            if recording_started is None:
                recording_started = current
            frame_seconds = current - start_time
            benchmark.log_frame(frame_seconds, input_to_render_seconds)
            if current - recording_started >= args.duration:
                running = False

pygame.quit()
if benchmark is not None:
    benchmark.close()
    print(f"Benchmark saved to {benchmark.path}")
