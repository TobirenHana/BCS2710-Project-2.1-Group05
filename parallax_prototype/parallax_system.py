import pygame
import json
import time
import math

try:
    with open("config.json", "r") as f:
        config = json.load(f)
except Exception:
    config = {
        "width": 800,
        "height": 600,
        "fps": 60,
        "far_factor": -0.05,
        "mid_factor": -0.3,
        "near_factor": -0.75
    }

pygame.init()
WIDTH = config["width"]
HEIGHT = config["height"]
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("2.5D Parallax with Realistic Shadow Deformation")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 16)

center_x = WIDTH // 2
center_y = HEIGHT // 2

eye_x = 0.0
eye_y = 0.0
running = True


FAR_W, FAR_H = 440, 320
far_base_surf = pygame.Surface((FAR_W, FAR_H), pygame.SRCALPHA)
pygame.draw.rect(far_base_surf, (10, 10, 15, 60), pygame.Rect(0, 0, FAR_W, FAR_H), border_radius=12)


MID_W, MID_H = 280, 200
mid_base_surf = pygame.Surface((MID_W, MID_H), pygame.SRCALPHA)
pygame.draw.rect(mid_base_surf, (10, 10, 15, 75), pygame.Rect(0, 0, MID_W, MID_H), border_radius=8)


BALL_RADIUS = 45
ball_base_surf = pygame.Surface((BALL_RADIUS * 2, BALL_RADIUS * 2), pygame.SRCALPHA)
pygame.draw.circle(ball_base_surf, (10, 10, 15, 90), (BALL_RADIUS, BALL_RADIUS), BALL_RADIUS)

while running:
    start_time = time.time()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            running = False

    mouse_x, mouse_y = pygame.mouse.get_pos()
    target_x = (mouse_x - center_x) / (WIDTH / 2)
    target_y = (mouse_y - center_y) / (HEIGHT / 2)

    eye_x += 0.2 * (target_x - eye_x)
    eye_y += 0.2 * (target_y - eye_y)

    screen.fill((30, 32, 45))

    max_offset_x = WIDTH * 0.25
    max_offset_y = HEIGHT * 0.25

    far_dx = int(eye_x * config["far_factor"] * max_offset_x)
    far_dy = int(eye_y * config["far_factor"] * max_offset_y)
    far_rect_x = center_x + far_dx - FAR_W // 2
    far_rect_y = center_y + far_dy - FAR_H // 2

    # 1.0 ~ 1.05
    dx_far_light = (center_x + far_dx) - mouse_x
    dy_far_light = (center_y + far_dy) - mouse_y
    far_stretch_w = int(FAR_W * (1.0 + min(abs(dx_far_light) / 3000.0, 0.05)))
    far_stretch_h = int(FAR_H * (1.0 + min(abs(dy_far_light) / 3000.0, 0.05)))
    scaled_far_shadow = pygame.transform.scale(far_base_surf, (far_stretch_w, far_stretch_h))

    far_s_offset_x = int(dx_far_light * 0.04)
    far_s_offset_y = int(dy_far_light * 0.04)
    screen.blit(scaled_far_shadow, (far_rect_x + far_s_offset_x, far_rect_y + far_s_offset_y))
    pygame.draw.rect(screen, (50, 60, 85), pygame.Rect(far_rect_x, far_rect_y, FAR_W, FAR_H), border_radius=12)

    mid_dx = int(eye_x * config["mid_factor"] * max_offset_x)
    mid_dy = int(eye_y * config["mid_factor"] * max_offset_y)
    mid_rect_x = center_x + mid_dx - MID_W // 2
    mid_rect_y = center_y + mid_dy - MID_H // 2

    #1.0 ~ 1.10
    dx_mid_light = (center_x + mid_dx) - mouse_x
    dy_mid_light = (center_y + mid_dy) - mouse_y
    mid_stretch_w = int(MID_W * (1.0 + min(abs(dx_mid_light) / 1800.0, 0.10)))
    mid_stretch_h = int(MID_H * (1.0 + min(abs(dy_mid_light) / 1800.0, 0.10)))
    scaled_mid_shadow = pygame.transform.scale(mid_base_surf, (mid_stretch_w, mid_stretch_h))

    mid_s_offset_x = int(dx_mid_light * 0.08)
    mid_s_offset_y = int(dy_mid_light * 0.08)
    screen.blit(scaled_mid_shadow, (mid_rect_x + mid_s_offset_x, mid_rect_y + mid_s_offset_y))
    pygame.draw.rect(screen, (85, 115, 160), pygame.Rect(mid_rect_x, mid_rect_y, MID_W, MID_H), border_radius=8)

    near_dx = int(eye_x * config["near_factor"] * max_offset_x)
    near_dy = int(eye_y * config["near_factor"] * max_offset_y)
    ball_x = center_x + near_dx
    ball_y = center_y + near_dy

    dx_ball_light = ball_x - mouse_x
    dy_ball_light = ball_y - mouse_y
    dist_ball = math.hypot(dx_ball_light, dy_ball_light)

    # max 1.35
    stretch = 1.0 + min(dist_ball / 600.0, 0.35)
    
    shadow_w = int(BALL_RADIUS * 2 * stretch)
    shadow_h = int(BALL_RADIUS * 2 * 0.95)

    stretched_ball_surf = pygame.transform.smoothscale(ball_base_surf, (shadow_w, shadow_h))

    if dist_ball > 3.0:
        angle = -math.degrees(math.atan2(dy_ball_light, dx_ball_light))
        rotated_ball_shadow = pygame.transform.rotate(stretched_ball_surf, angle)
    else:
        rotated_ball_shadow = stretched_ball_surf

    ball_s_offset_x = int(dx_ball_light * 0.12)
    ball_s_offset_y = int(dy_ball_light * 0.12)

    shadow_rect = rotated_ball_shadow.get_rect(
        center=(ball_x + ball_s_offset_x, ball_y + ball_s_offset_y)
    )
    screen.blit(rotated_ball_shadow, shadow_rect.topleft)
    pygame.draw.circle(screen, (245, 195, 70), (ball_x, ball_y), BALL_RADIUS)

    clock.tick(config["fps"])
    latency_ms = (time.time() - start_time) * 1000
    fps = clock.get_fps()

    text_fps = font.render(f"FPS: {fps:.1f}", True, (210, 215, 220))
    text_lat = font.render(f"Latency: {latency_ms:.2f} ms", True, (210, 215, 220))
    text_pos = font.render(f"Eye: ({eye_x:.2f}, {eye_y:.2f})", True, (210, 215, 220))

    screen.blit(text_fps, (20, 20))
    screen.blit(text_lat, (20, 40))
    screen.blit(text_pos, (20, 60))

    pygame.display.flip()

pygame.quit()