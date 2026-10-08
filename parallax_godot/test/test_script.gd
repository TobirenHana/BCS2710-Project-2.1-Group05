
extends Node

# Godot 2D automatic benchmarks
# Attach to a child Node named Benchmark.

@export var normal_duration: float = 60.0
@export var stability_duration: float = 300.0
@export var warmup: float = 5.0
@export var automatic_movement: bool = true

const RESOLUTION = Vector2i(1280, 720)

var tests: Array[Dictionary] = []
var test_index: int = 0
var elapsed: float = 0.0
var frame_index: int = 0
var csv: FileAccess

var output_folder: String = ""
var scene_2d: Node2D
var extra_objects: Node2D
var original_factors: Dictionary = {}
var parallax_enabled: bool = true
var running: bool = false


func _ready() -> void:
	process_priority = 100
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	call_deferred("start_benchmarks")


func start_benchmarks() -> void:
	Engine.max_fps = 60
	get_window().size = RESOLUTION
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

	scene_2d = get_parent() as Node2D

	if scene_2d == null:
		push_error("Benchmark must be a child of a Node2D.")
		return

	scene_2d.benchmark_mode = true

	var settings: Dictionary = scene_2d.get("config")

	for key in ["far_factor", "mid_factor", "near_factor"]:
		if settings.has(key):
			original_factors[key] = settings[key]

	extra_objects = Node2D.new()
	extra_objects.name = "BenchmarkExtraObjects"
	scene_2d.add_child(extra_objects)


	output_folder = "C:/Users/gamef/Desktop/BCS2710-Project-2.1-Group05/parallax_godot_3D/test/2D/"

	var error := DirAccess.make_dir_recursive_absolute(output_folder)


	if error != OK:
		push_error("Could not create benchmark folder.")
		return

	# Basic performance
	tests.append({
		"name": "basic",
		"objects": 3,
		"parallax": true,
		"duration": normal_duration
	})

	# Complexity tests
	for amount in [5, 20, 50]:
		tests.append({
			"name": "complexity",
			"objects": amount,
			"parallax": true,
			"duration": normal_duration
		})

	# Parallax on and off
	for enabled in [true, false]:
		tests.append({
			"name": "parallax",
			"objects": 3,
			"parallax": enabled,
			"duration": normal_duration
		})

	# Stability test
	tests.append({
		"name": "stability",
		"objects": 3,
		"parallax": true,
		"duration": stability_duration
	})

	print("Starting ", tests.size(), " benchmarks.")
	print("Results folder: ", output_folder)

	start_next_test()



func start_next_test() -> void:
	if test_index >= tests.size():
		running = false

		if csv != null:
			csv.close()
			csv = null

		print("ALL BENCHMARKS COMPLETED!")
		print("Saved to: ", output_folder.path_join("2D.csv"))
		get_tree().quit()
		return

	var test: Dictionary = tests[test_index]

	elapsed = 0.0
	frame_index = 0
	parallax_enabled = test["parallax"]

	configure_parallax(parallax_enabled)
	configure_objects(int(test["objects"]))

	if csv == null:
		csv = FileAccess.open(
			output_folder.path_join("2D.csv"),
			FileAccess.WRITE
		)

		if csv == null:
			push_error("Could not create 2D.csv")
			get_tree().quit()
			return

		csv.store_csv_line(PackedStringArray([
			"frame_index",
			"test",
			"object_count",
			"parallax_enabled",
			"frame_time_ms",
			"fps",
			"memory_mb",
			"process_time_ms"
		]))

	running = true

	print("Running test ", test_index + 1, "/", tests.size(), ": ", test["name"])



func configure_parallax(enabled: bool) -> void:
	var settings: Dictionary = scene_2d.get("config")

	for key in original_factors:
		if enabled:
			settings[key] = original_factors[key]
		else:
			settings[key] = 0.0

	scene_2d.set("config", settings)

	if not enabled:
		scene_2d.set("eye", Vector2.ZERO)


func configure_objects(count: int) -> void:
	for child in extra_objects.get_children():
		extra_objects.remove_child(child)
		child.queue_free()

	for i in range(count):
		var obj := Polygon2D.new()
		var vertices := PackedVector2Array()

		for j in range(16):
			var angle := TAU * float(j) / 16.0

			vertices.append(
				Vector2(cos(angle), sin(angle)) * 9.0
			)

		obj.polygon = vertices
		obj.color = Color(0.3, 0.75, 0.9)

		obj.position = Vector2(
			45 + (i % 10) * 110,
			115 + int(i / 10) * 70
		)

		extra_objects.add_child(obj)



func _process(delta: float) -> void:
	if not running or csv == null:
		return

	elapsed += delta

	var test: Dictionary = tests[test_index]
	var duration: float = test["duration"]

	if elapsed >= warmup + duration:
		test_index += 1
		start_next_test()
		return

	# Automatic movement without controlling the mouse
	if automatic_movement and parallax_enabled:
		var normalized := Vector2(
			sin(elapsed * 0.7),
			sin(elapsed * 1.4) * 0.7
		)

		scene_2d.benchmark_eye = normalized
	else:
		scene_2d.benchmark_eye = Vector2.ZERO

	if elapsed < warmup:
		return

	var frame_ms := delta * 1000.0
	var fps := 1.0 / delta if delta > 0.0 else 0.0

	var memory_mb := float(
		Performance.get_monitor(
			Performance.MEMORY_STATIC
		)
	) / 1048576.0

	var process_ms := float(
		Performance.get_monitor(
			Performance.TIME_PROCESS
		)
	) * 1000.0

	csv.store_csv_line(PackedStringArray([
		str(frame_index),
		str(test["name"]),
		str(test["objects"]),
		str(parallax_enabled),
		str(frame_ms),
		str(fps),
		str(memory_mb),
		str(process_ms)
	]))

	frame_index += 1



func _exit_tree() -> void:
	if csv != null:
		csv.close()
