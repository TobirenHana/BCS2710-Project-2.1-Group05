extends Node2D
var config := {
	"width": 960, "height": 640, "fps": 60,
	"far_factor": -0.04, "mid_factor": -0.28, "near_factor": -0.70
}

var WIDTH: int
var HEIGHT: int
var center: Vector2
var eye := Vector2.ZERO

var benchmark_mode: bool = false
var benchmark_eye := Vector2.ZERO

const BALL_RADIUS := 45.0
const BALL_SH_PAD := 16.0
var BALL_SH_DIM: float

var ball_base_shadow: ImageTexture
var ball_ambient: ImageTexture
var font: Font

var _frame_start_usec: int = 0
var _latency_ms: float = 0.0

func _ready() -> void:
	_load_config()
	WIDTH = config["width"]
	HEIGHT = config["height"]
	get_window().size = Vector2i(WIDTH, HEIGHT)
	get_window().title = "2.5D Parallax - Rounded Box Perspective Shadows"
	Engine.max_fps = config["fps"]
	center = Vector2(WIDTH, HEIGHT) / 2.0

	BALL_SH_DIM = (BALL_RADIUS + BALL_SH_PAD) * 2.0
	ball_base_shadow = _build_ball_shadow_texture()
	ball_ambient = _build_ball_ambient_texture()
	font = ThemeDB.fallback_font
	
func _process(_delta: float) -> void:
	_frame_start_usec = Time.get_ticks_usec()

	var target: Vector2

	if benchmark_mode:
		target = benchmark_eye
	else:
		var mouse := get_viewport().get_mouse_position()
		target = Vector2(
			(mouse.x - center.x) / (WIDTH / 2.0),
			(mouse.y - center.y) / (HEIGHT / 2.0)
		)

	eye += 0.2 * (target - eye)
	queue_redraw()

func _load_config() -> void:
	var path := "res://config.json"
	if not FileAccess.file_exists(path):
		return
	var f := FileAccess.open(path, FileAccess.READ)
	var parsed = JSON.parse_string(f.get_as_text())
	if typeof(parsed) == TYPE_DICTIONARY:
		for key in parsed.keys():
			config[key] = parsed[key]
			
func _blend_pixel(img: Image, x: int, y: int, c: Color) -> void:
	if x < 0 or y < 0 or x >= img.get_width() or y >= img.get_height():
		return
	var dst := img.get_pixel(x, y)
	var out := dst.lerp(c, c.a)
	out.a = dst.a + c.a * (1.0 - dst.a)
	img.set_pixel(x, y, out)
	
func _fill_circle(img: Image, c: Vector2, radius: float, color: Color) -> void:
	var x0 := int(c.x - radius); var x1 := int(c.x + radius)
	var y0 := int(c.y - radius); var y1 := int(c.y + radius)
	for y in range(y0, y1 + 1):
		for x in range(x0, x1 + 1):
			if Vector2(x, y).distance_to(c) <= radius:
				_blend_pixel(img, x, y, color)

func _build_ball_shadow_texture() -> ImageTexture:
	var dim := int(BALL_SH_DIM)
	var img := Image.create(dim, dim, false, Image.FORMAT_RGBA8)
	var r := int(BALL_RADIUS + BALL_SH_PAD)
	while r > BALL_RADIUS - 6:
		var factor: float = clamp(1.0 - (r - BALL_RADIUS + 6) / (BALL_SH_PAD + 12), 0.0, 1.0)
		var alpha := (115.0 * pow(factor, 1.5)) / 255.0
		_fill_circle(img, Vector2(dim / 2.0, dim / 2.0), r, Color(4/255.0, 6/255.0, 12/255.0, alpha))
		r -= 2
	return ImageTexture.create_from_image(img)
	
func _build_ball_ambient_texture() -> ImageTexture:
	var dim := int(BALL_RADIUS * 2)
	var img := Image.create(dim, dim, false, Image.FORMAT_RGBA8)
	var r := int(BALL_RADIUS)
	while r > 4:
		var alpha := (28.0 * (1.0 - float(r) / BALL_RADIUS)) / 255.0
		_fill_circle(img, Vector2(BALL_RADIUS - 8, BALL_RADIUS - 8), r, Color(1, 1, 1, alpha))
		r -= 2
	return ImageTexture.create_from_image(img)

func get_rounded_rect_vertices(rect: Rect2, radius: float, points_per_corner: int = 6) -> PackedVector2Array:
	var rx := rect.position.x; var ry := rect.position.y
	var rw := rect.size.x; var rh := rect.size.y
	var r: float = min(radius, min(rw / 2.0, rh / 2.0))
	var vertices := PackedVector2Array()

	var corners = [
		[rx + rw - r, ry + r, 0.0, PI * 0.5],
		[rx + rw - r, ry + rh - r, PI * 0.5, PI],
		[rx + r, ry + rh - r, PI, PI * 1.5],
		[rx + r, ry + r, PI * 1.5, PI * 2.0],
	]

	for c in corners:
		for i in range(points_per_corner):
			var theta = c[2] + (c[3] - c[2]) * (float(i) / (points_per_corner - 1))
			vertices.append(Vector2(c[0] + r * sin(theta), c[1] - r * cos(theta)))

	return vertices

func _project_vertices(orig: PackedVector2Array, light_pos: Vector2, height_ratio: float, scale_mod: float) -> PackedVector2Array:
	var proj := PackedVector2Array()
	for v in orig:
		proj.append(v + (v - light_pos) * (height_ratio * scale_mod))
	return proj


func render_rounded_perspective_shadow(
	rect: Rect2,
	corner_radius: float,
	light_pos: Vector2,
	height_ratio: float,
	base_alpha: float
) -> void:

	var orig := get_rounded_rect_vertices(rect, corner_radius)
	var n := orig.size()

	var penumbra := _project_vertices(
		orig, light_pos, height_ratio, 1.18
	)

	if Geometry2D.triangulate_polygon(penumbra).size() >= 3:
		draw_colored_polygon(
			penumbra,
			Color(5/255.0, 8/255.0, 14/255.0,
				(base_alpha * 0.35) / 255.0)
		)

	var umbra := _project_vertices(
		orig, light_pos, height_ratio, 1.0
	)

	if Geometry2D.triangulate_polygon(umbra).size() >= 3:
		draw_colored_polygon(
			umbra,
			Color(3/255.0, 4/255.0, 8/255.0,
				(base_alpha * 0.85) / 255.0)
		)

	for i in range(n):
		var j := (i + 1) % n

		var p1 := orig[i]
		var p2 := orig[j]

		var mid := (p1 + p2) * 0.5

		var normal := Vector2(
			-(p2.y - p1.y),
			p2.x - p1.x
		)

		if (mid - light_pos).dot(normal) > 0.0:
			var quad := PackedVector2Array([
				p1, p2, umbra[j], umbra[i]
			])

			if Geometry2D.triangulate_polygon(quad).size() >= 3:
				draw_colored_polygon(
					quad,
					Color(4/255.0, 5/255.0, 10/255.0,
						(base_alpha * 0.55) / 255.0)
				)



func draw_rounded_rect(rect: Rect2, radius: float, color: Color) -> void:
	draw_colored_polygon(get_rounded_rect_vertices(rect, radius), color)

func draw_rounded_rect_outline(rect: Rect2, radius: float, color: Color, width: float) -> void:
	var v := get_rounded_rect_vertices(rect, radius)
	v.append(v[0])
	draw_polyline(v, color, width, true)

func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, Vector2(WIDTH, HEIGHT)), Color8(26, 29, 41))

	var max_offset := Vector2(WIDTH * 0.22, HEIGHT * 0.22)
	var mouse: Vector2

	if benchmark_mode:
		mouse = center + eye * Vector2(WIDTH / 2.0, HEIGHT / 2.0)
	else:
		mouse = get_viewport().get_mouse_position()

	# Far layer
	var far_size := Vector2(480, 330)
	var far_rect := Rect2(center + eye * config["far_factor"] * max_offset - far_size / 2.0, far_size)
	render_rounded_perspective_shadow(far_rect, 12.0, mouse, 0.025, 80.0)
	draw_rounded_rect(far_rect, 12.0, Color8(46, 54, 74))

	# Mid layer
	var mid_size := Vector2(290, 195)
	var mid_rect := Rect2(center + eye * config["mid_factor"] * max_offset - mid_size / 2.0, mid_size)
	render_rounded_perspective_shadow(mid_rect, 10.0, mouse, 0.075, 120.0)
	draw_rounded_rect(mid_rect, 10.0, Color8(74, 102, 146))
	draw_rounded_rect_outline(mid_rect, 10.0, Color8(98, 128, 178), 1.0)

	# Near layer (ball)
	var ball_pos : Vector2 = center + eye * config["near_factor"] * max_offset
	_draw_ball(ball_pos, mouse)
	_draw_hud()
	
func _draw_ball(ball_pos: Vector2, mouse: Vector2) -> void:
	var diff := ball_pos - mouse
	var dist := diff.length()
	var stretch: float = 1.0 + min(dist / 900.0, 0.25)
	var angle := 0.0
	if dist > 1.5:
		angle = diff.angle()

	var shadow_center := ball_pos + diff * 0.10
	draw_set_transform(shadow_center, angle, Vector2(stretch, 1.0))
	draw_texture(ball_base_shadow, -Vector2(BALL_SH_DIM, BALL_SH_DIM) / 2.0)
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)   # reset — see callout

	draw_circle(ball_pos, BALL_RADIUS, Color8(242, 186, 52))
	draw_texture(ball_ambient, ball_pos - Vector2(BALL_RADIUS, BALL_RADIUS))
	
func _draw_hud() -> void:
	_latency_ms = (Time.get_ticks_usec() - _frame_start_usec) / 1000.0
	var c := Color8(210, 215, 220)
	draw_string(font, Vector2(25, 32), "FPS: %.1f" % Engine.get_frames_per_second(), HORIZONTAL_ALIGNMENT_LEFT, -1, 15, c)
	draw_string(font, Vector2(25, 52), "Render Latency: %.2f ms" % _latency_ms, HORIZONTAL_ALIGNMENT_LEFT, -1, 15, c)
	draw_string(font, Vector2(25, 72), "Eye Norm: (%.2f, %.2f)" % [eye.x, eye.y], HORIZONTAL_ALIGNMENT_LEFT, -1, 15, c)
