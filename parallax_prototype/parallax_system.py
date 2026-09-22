import pygame
import json
import time

# load settings from json file
try:
    with open("config.json", "r") as f:
        config = json.load(f)
except:
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
pygame.display.set_caption("2.5D Parallax Prototype")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 16)

center_x = WIDTH // 2
center_y = HEIGHT // 2

# current smooth eye coordinates
eye_x = 0.0
eye_y = 0.0

running = True
while running:
    start_time = time.time()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            running = False

    # simulate eye tracking using mouse position
    # map to normalized range [-1.0, 1.0]
    mouse_x, mouse_y = pygame.mouse.get_pos()
    target_x = (mouse_x - center_x) / (WIDTH / 2)
    target_y = (mouse_y - center_y) / (HEIGHT / 2)

    # basic smoothing so it doesn't jitter too much
    eye_x += 0.2 * (target_x - eye_x)
    eye_y += 0.2 * (target_y - eye_y)

    screen.fill((25, 25, 35))

    # calculate offsets for different depth layers
    max_offset_x = WIDTH * 0.25
    max_offset_y = HEIGHT * 0.25

    # 1. far layer (background, moves slowly)
    far_dx = int(eye_x * config["far_factor"] * max_offset_x)
    far_dy = int(eye_y * config["far_factor"] * max_offset_y)
    pygame.draw.rect(
        screen,
        (65, 80, 110),
        pygame.Rect(center_x + far_dx - 200, center_y + far_dy - 150, 400, 300),
        border_radius=10
    )

    # 2. mid layer
    mid_dx = int(eye_x * config["mid_factor"] * max_offset_x)
    mid_dy = int(eye_y * config["mid_factor"] * max_offset_y)
    pygame.draw.rect(
        screen,
        (110, 145, 190),
        pygame.Rect(center_x + mid_dx - 120, center_y + mid_dy - 90, 240, 180),
        border_radius=8
    )

    # 3. near layer (foreground, moves fastest)
    near_dx = int(eye_x * config["near_factor"] * max_offset_x)
    near_dy = int(eye_y * config["near_factor"] * max_offset_y)
    pygame.draw.circle(
        screen,
        (245, 195, 70),
        (center_x + near_dx, center_y + near_dy),
        40
    )

    # performance counter
    clock.tick(config["fps"])
    latency_ms = (time.time() - start_time) * 1000
    fps = clock.get_fps()

    # debug text
    text_fps = font.render(f"FPS: {fps:.1f}", True, (210, 215, 220))
    text_lat = font.render(f"Latency: {latency_ms:.2f} ms", True, (210, 215, 220))
    text_pos = font.render(f"Eye: ({eye_x:.2f}, {eye_y:.2f})", True, (210, 215, 220))

    screen.blit(text_fps, (20, 20))
    screen.blit(text_lat, (20, 40))
    screen.blit(text_pos, (20, 60))

    pygame.display.flip()

pygame.quit()
