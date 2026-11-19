extends Node2D
const VIDEO_WIDTH=1080
const VIDEO_HEIGHT=1920
const Rig = preload("res://scripts/rig.gd")
var data: Dictionary
var actors: Dictionary = {}
var backgrounds: Dictionary = {}
var camera := Camera2D.new()
var frame := 0
var caption := Sprite2D.new()
var caption_textures: Dictionary = {}
var visible_caption := ""
var last_source := ""
var trace: FileAccess

func shot_participants(scene: Dictionary) -> Array:
	var visible:Array=scene.visible_characters
	var shot:Dictionary=scene.camera
	var target_id:String=str(shot.get("target",""))
	if shot.shot in ["wide","establishing","tracking"] or target_id not in visible:return visible.duplicate()
	var selected:Array=[target_id]
	if shot.shot in ["two_shot","over_shoulder"] and shot.get("partner","") in visible:selected.append(shot.partner)
	return selected

func shot_target(shot: Dictionary, w: float, h: float) -> Array:
	var target:=Vector2(w/2.0,h/2.0)
	var zoom:=1.0
	if shot.shot in ["close_up","medium"] and not actors.has(shot.get("target","")):zoom=1.22
	if shot.shot in ["close_up","reaction","medium","over_shoulder"] and actors.has(shot.get("target","")):
		var actor=actors[shot.target]
		target=actor.position+Vector2(0,-260)
		zoom=1.28 if shot.shot!="close_up" else 1.48
		zoom=minf(zoom,1.48 if shot.shot=="close_up" else 1.28)
	if shot.shot=="two_shot" and actors.has(shot.get("target","")) and actors.has(shot.get("partner","")):
		var left=actors[shot.target];var right=actors[shot.partner]
		target=(left.position+right.position)/2.0+Vector2(0,-240)
		zoom=minf(1.60,w/(absf(left.position.x-right.position.x)+210.0))
		zoom=maxf(1.0,zoom)
	var half:=Vector2(w,h)/(2.0*zoom)
	target=Vector2(clampf(target.x,half.x,w-half.x),clampf(target.y,half.y,h-half.y))
	return [target,zoom]

func load_texture(path: String) -> Texture2D:
	return ImageTexture.create_from_image(Image.load_from_file(path))

func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	data=JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	if not portrait_canvas():return
	if data.has("trace_file"):trace=FileAccess.open(data.trace_file,FileAccess.WRITE)
	var w: float=data.stage_width;var h: float=data.stage_height
	for id in data.backgrounds:
		var bg := Sprite2D.new()
		bg.texture=load_texture(data.backgrounds[id].file)
		bg.position=Vector2(w/2.0,h/2.0)
		var factor := maxf(w/bg.texture.get_width(),h/bg.texture.get_height())
		bg.scale=Vector2.ONE*factor
		add_child(bg);backgrounds[id]=bg
		if data.backgrounds[id].get("foreground")!=null:
			var fg:=Sprite2D.new();fg.texture=load_texture(data.backgrounds[id].foreground)
			fg.z_as_relative=false;fg.z_index=100;bg.add_child(fg)
	for description in data.characters:
		var actor=Rig.new()
		add_child(actor)
		actor.setup(description,0.80)
		actors[description.id]=actor
	add_child(camera)
	camera.position=Vector2(w/2.0,h/2.0)
	camera.zoom=Vector2.ONE*float(data.width)/float(data.stage_width)
	camera.position_smoothing_enabled=false
	var canvas := CanvasLayer.new();add_child(canvas)
	canvas.add_child(caption)
	evaluate(float(data.start_frame)/data.fps)

func portrait_canvas() -> bool:
	var valid:bool=(int(data.width)==1080 and int(data.height)==1920) or (int(data.width)==720 and int(data.height)==1280)
	if not valid or int(data.fps)!=30:
		push_error("Portrait-only renderer rejected dimensions "+str(data.width)+"x"+str(data.height));get_tree().quit(2);return false
	get_window().size=Vector2i(int(data.width),int(data.height))
	return true

func update_caption(scene: Dictionary,t: float,w: float,h: float) -> void:
	var cue: Dictionary=scene.get("subtitle",{}) if scene.kind=="speech" else scene.get("screen_text_asset",{})
	caption.visible=not cue.is_empty() and t>=cue.start and t<cue.end
	visible_caption=""
	if not caption.visible:return
	visible_caption=cue.text
	if not caption_textures.has(cue.file):caption_textures[cue.file]=load_texture(cue.file)
	caption.texture=caption_textures[cue.file]
	caption.position=Vector2(w/2.0,h-float(cue.bottom_margin)-float(cue.image_height)/2.0)

func interval(t: float) -> Dictionary:
	for segment in data.direction:
		if t>=segment.start and t<segment.end:return segment
	return data.direction.back()

func mouth_value(cues: Array, time: float) -> Array:
	for i in range(cues.size()):
		var cue: Dictionary=cues[i]
		if time>=cue.start and time<cue.end:
			var remaining: float=cue.end-time
			var next: String=cues[i+1].value if i+1<cues.size() else "X"
			return [cue.value,next,clampf((0.035-remaining)/0.035,0.0,1.0)]
	return ["X","",0.0]

func evaluate(t: float) -> void:
	var scene:=interval(t)
	var current_index:int=data.direction.find(scene)
	var prior_bg:String=data.direction[current_index-1].background_id if current_index>0 else scene.background_id
	var dissolve:float=smoothstep(0.0,1.0,clampf((t-scene.start)/0.3,0.0,1.0))
	for id in backgrounds:
		var bg:Sprite2D=backgrounds[id]
		bg.visible=id==scene.background_id or (id==prior_bg and prior_bg!=scene.background_id and dissolve<1.0)
		bg.z_index=0 if id==scene.background_id else -1
		bg.modulate.a=dissolve if id==scene.background_id and prior_bg!=scene.background_id else 1.0
	var w:float=data.stage_width;var h:float=data.stage_height
	update_caption(scene,t,data.width,data.height)
	var visible: Array=scene.visible_characters
	for id in actors:
		var actor=actors[id]
		actor.visible=id in shot_participants(scene)
		if id not in visible:continue
		var cue:Dictionary=scene.actors[id]
		var index:=visible.find(id)
		# Use the stage width; inward-only spacing made a short walk overlap
		# the neighbouring child's head and talking gesture.
		var x:float=(index+0.5)*w/visible.size()
		cue["base_x"]=x
		var y:float=h-340.0
		var phase:float=clampf((t-cue.start)/maxf(0.01,cue.end-cue.start),0.0,1.0)
		var easing:float=smoothstep(0.0,1.0,phase)
		actor.position=Vector2(x+lerpf(cue.get("from_x",0.0),cue.get("to_x",0.0),easing),y)
		var mouth:Array=["X","",0.0]
		if id==scene.get("speaker","") and not scene.get("off_screen",true):mouth=mouth_value(scene.get("mouth_cues",[]),t-scene.start)
		actor.act(t,cue,mouth[0],mouth[1],mouth[2])
		if trace!=null and frame%3==0:
			var left:Vector2=actor.bones.LeftFoot.global_position
			var right:Vector2=actor.bones.RightFoot.global_position
			trace.store_line(JSON.stringify({"frame":int(round(t*data.fps)),"character":id,"action":cue.action,
				"root_x":actor.position.x,"left_ankle":[left.x,left.y],"right_ankle":[right.x,right.y],
				"left_knee":actor.bones.LeftLeg.rotation,"right_knee":actor.bones.RightLeg.rotation,
				"elbow":actor.bones.RightForearm.rotation,"torso":actor.bones.Torso.rotation,"head":actor.bones.Head.rotation,"mouth":mouth[0],"ground":y,"walk_phase":actor.walk_phase,"walking":actor.walking_now,"subtitle_visible":caption.visible,"subtitle_text":visible_caption}))
	var target:Array=shot_target(scene.camera,w,h)
	var previous:Array=[Vector2(w/2.0,h/2.0),1.0]
	var scene_index:int=data.direction.find(scene)
	if scene_index>0 and data.direction[scene_index-1].source_scene_id==scene.source_scene_id:previous=shot_target(data.direction[scene_index-1].camera,w,h)
	var camera_ease:=smoothstep(0.0,1.0,clampf((t-scene.start)/0.45,0.0,1.0))
	# Scene-authored camera values are deterministic; no wall-clock smoothing.
	camera.position=previous[0].lerp(target[0],camera_ease)
	camera.zoom=Vector2.ONE*lerpf(previous[1],target[1],camera_ease)*float(data.width)/float(data.stage_width)

func _process(_delta: float) -> void:
	# CLI iterations can include startup before this scene is ready. Count actual
	# scene frames; capture two real overscan frames and trim them in FFmpeg.
	if frame>=int(data.end_frame)-int(data.start_frame)+2:
		get_tree().quit();return
	var t:float=(float(data.start_frame)+frame)/data.fps
	evaluate(t)
	frame+=1
	if frame%10==0:
		var file:=FileAccess.open(data.progress_file,FileAccess.WRITE)
		file.store_string(str(frame));file.close()
