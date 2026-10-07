extends Camera3D
## Attach to a Camera3D. The camera drifts around the focus point based on the
## cursor position, but always stays aimed at the focus point (default 0,0,0).
## Written for Godot 4.x.

@export var focus_point: Vector3 = Vector3.ZERO
@export_range(0.0, 90.0) var max_yaw_degrees: float = 15.0    # left/right sway
@export_range(0.0, 60.0) var max_pitch_degrees: float = 10.0  # up/down sway
@export var smoothing: float = 5.0        # higher = snappier, lower = floatier
@export var invert_x: bool = false
@export var invert_y: bool = false

var _base_offset: Vector3   # camera position relative to the focus point at start
var _up_axis: Vector3 = Vector3.UP
var _yaw: float = 0.0
var _pitch: float = 0.0


func _ready() -> void:
	_base_offset = global_position - focus_point

	# Camera is sitting on the focus point: there's nothing to orbit, so back it off.
	if _base_offset.length() < 0.01:
		push_warning("Camera is at the focus point; moving it back 6 units on Z. Move the camera in the editor to set your own distance.")
		_base_offset = Vector3(0, 0, 6)

	# Camera is straight above/below the focus point: UP would be parallel to the view
	# direction, so use -Z as the reference "up" instead.
	if absf(_base_offset.normalized().dot(Vector3.UP)) > 0.999:
		_up_axis = Vector3.FORWARD


func _process(delta: float) -> void:
	var viewport := get_viewport()
	var size := viewport.get_visible_rect().size
	var mouse := viewport.get_mouse_position()

	# Normalize cursor to -1..1 (center of the screen = 0,0)
	var n := ((mouse / size) - Vector2(0.5, 0.5)) * 2.0
	n = n.clamp(Vector2(-1, -1), Vector2(1, 1))
	if invert_x: n.x = -n.x
	if invert_y: n.y = -n.y

	var target_yaw := deg_to_rad(n.x * max_yaw_degrees)
	var target_pitch := deg_to_rad(n.y * max_pitch_degrees)

	# Frame-rate independent smoothing
	var t := 1.0 - exp(-smoothing * delta)
	_yaw = lerp(_yaw, target_yaw, t)
	_pitch = lerp(_pitch, target_pitch, t)

	# Swing around the focus point: yaw around the up axis, then pitch around the right axis
	var offset := _base_offset.rotated(_up_axis, _yaw)
	var right := _up_axis.cross(offset)
	if right.length() > 0.0001:
		offset = offset.rotated(right.normalized(), _pitch)

	global_position = focus_point + offset
	look_at(focus_point, _up_axis)
