extends Node2D
## Articulated rigid cutout: original PNG pixels on nested Bone2D pivots.
var data: Dictionary
var bones: Dictionary = {}
var sprites: Dictionary = {}
var rest: Dictionary = {}
var tree: AnimationTree
var playback: AnimationNodeStateMachinePlayback
var current_state := "idle"
var skeleton := Skeleton2D.new()
var base_scale := 1.0
var identity := ""
var expression := "neutral"
var clip_names: Array = []
var last_time := -1.0
var motion_version := 2
var walk_phase := 0.0
var walking_now := false

func texture(path: String) -> Texture2D:
	var image := Image.load_from_file(path)
	return ImageTexture.create_from_image(image)

func setup(description: Dictionary, screen_scale: float) -> void:
	data = description.rig
	identity = description.id
	motion_version = int(description.get("motion_version",2))
	base_scale = screen_scale
	skeleton.name = "Skeleton2D"
	add_child(skeleton)
	var shadow:=Polygon2D.new()
	var vertices:=PackedVector2Array()
	for i in range(32):vertices.append(Vector2(cos(i*TAU/32.0)*72.0,sin(i*TAU/32.0)*10.0))
	shadow.polygon=vertices;shadow.color=Color(0.03,0.05,0.07,0.22);shadow.z_index=-1
	add_child(shadow)
	skeleton.position = -Vector2(data.feet[0],data.feet[1])
	for key in data.bones:
		var item: Dictionary = data.bones[key]
		var bone := Bone2D.new()
		bone.name = key
		bone.set_autocalculate_length_and_angle(false)
		bone.length = 60.0
		var absolute := Vector2(item.position[0],item.position[1])
		var parent_name = item.parent
		if parent_name != null:
			bones[parent_name].add_child(bone)
			var parent_position = data.bones[parent_name].position
			bone.position = absolute - Vector2(parent_position[0],parent_position[1])
		else:
			skeleton.add_child(bone)
			bone.position = absolute
		bone.rest = bone.transform
		bones[key] = bone
		rest[key] = bone.position
	# Explicit ordering keeps back hair/limbs behind the torso, face in front.
	var order := ["hair_back","left_thigh","left_leg","left_foot","right_thigh","right_leg","right_foot","left_upper_arm","left_forearm","left_hand","torso","right_upper_arm","right_forearm","right_hand","head","hair","eyes_open","pupils","eyes_closed","brows"]
	for mouth in "ABCDEFGHX": order.append("mouth_"+mouth)
	for key in order:
		if not data.parts.has(key): continue
		var part: Dictionary = data.parts[key]
		var sprite := Sprite2D.new()
		sprite.name = key
		sprite.centered = false
		sprite.texture = texture(description.directory+"/"+part.file)
		var pivot = data.bones[part.bone].position
		sprite.position = Vector2(part.origin[0]-pivot[0],part.origin[1]-pivot[1])
		sprite.z_as_relative = false
		sprite.z_index = order.find(key)+2
		bones[part.bone].add_child(sprite)
		sprites[key] = sprite
	build_state_machine()
	scale = Vector2.ONE*base_scale

func build_state_machine() -> void:
	var player := AnimationPlayer.new()
	player.name = "AnimationPlayer"
	add_child(player)
	var library := AnimationLibrary.new()
	var states := AnimationNodeStateMachine.new()
	var actions := ["idle","walk","run","stop","talk","wave","point","raise_hand","fold_arms","scratch_head","touch_chin","look_around","explain","confused","celebrate","fear","sit","stand_up","step_back","move_closer","move_away","turn"]
	clip_names=actions
	for action in actions:
		var animation := Animation.new()
		animation.length = 2.0
		animation.loop_mode = Animation.LOOP_LINEAR
		var track := animation.add_track(Animation.TYPE_VALUE)
		animation.track_set_path(track,NodePath("Skeleton2D/Hips/Torso:rotation"))
		var amount := 0.006 if action=="idle" else 0.015
		for i in range(9):animation.track_insert_key(track,i/4.0,sin(i*PI/4.0)*amount)
		library.add_animation(action,animation)
		var node := AnimationNodeAnimation.new()
		node.animation = action
		var blend := AnimationNodeBlendTree.new()
		blend.add_node("Clip",node)
		blend.add_node("Clock",AnimationNodeTimeSeek.new())
		blend.connect_node("Clock",0,"Clip")
		blend.connect_node("output",0,"Clock")
		states.add_node(action,blend)
	for a in actions:
		for b in actions:
			if a==b:continue
			var transition := AnimationNodeStateMachineTransition.new()
			transition.xfade_time = 0.18
			states.add_transition(a,b,transition)
	player.add_animation_library("",library)
	tree = AnimationTree.new()
	tree.name = "AnimationTree"
	tree.anim_player = NodePath("../AnimationPlayer")
	tree.tree_root = states
	tree.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	add_child(tree)
	tree.active = true
	playback = tree.get("parameters/playback")
	playback.start("idle")

func smooth01(value: float) -> float:
	return smoothstep(0.0,1.0,clamp(value,0.0,1.0))

func root_x_at(local: float, cue: Dictionary) -> float:
	var span: float=maxf(0.01,float(cue.end)-float(cue.start))
	return float(cue.get("base_x",position.x))+lerpf(float(cue.get("from_x",0.0)),float(cue.get("to_x",0.0)),smooth01(local/span))

func inverse_smooth(value: float) -> float:
	var low := 0.0;var high := 1.0
	for _i in range(24):
		var middle:float=(low+high)/2.0
		if smooth01(middle)<clampf(value,0.0,1.0):low=middle
		else:high=middle
	return (low+high)/2.0

func solve_leg(side: String, target: Vector2, bend: float) -> void:
	var upper: Bone2D = bones[side+"Thigh"]
	var lower: Bone2D = bones[side+"Leg"]
	var foot: Bone2D = bones[side+"Foot"]
	var a: float = rest[side+"Leg"].length()
	var b: float = rest[side+"Foot"].length()
	var delta: Vector2 = upper.get_parent().to_local(target)-upper.position
	if motion_version>=2 and delta.length()>a+b-0.5:
		# Subpixel reach compensation keeps a planted foot fixed during hip bounce.
		var reach:float=minf(1.03,(delta.length()+0.5)/(a+b))
		lower.position=rest[side+"Leg"]*reach;foot.position=rest[side+"Foot"]*reach
		a*=reach;b*=reach
	var distance := clampf(delta.length(),absf(a-b)+1.0,a+b-0.5)
	var base: float = delta.angle()
	var knee := acos(clampf((a*a+distance*distance-b*b)/(2.0*a*distance),-1.0,1.0))
	upper.rotation = base-PI/2.0-bend*knee
	lower.rotation = bend*(PI-acos(clampf((a*a+b*b-distance*distance)/(2.0*a*b),-1.0,1.0)))
	foot.rotation = -upper.global_rotation-lower.rotation+upper.rotation
	# Keep the shoe level in world coordinates, including torso/root mirroring.
	foot.global_rotation = 0.0

func act(t: float, cue: Dictionary, mouth: String, mouth_next: String="", mouth_blend: float=0.0) -> void:
	var action: String = cue.get("action","idle")
	if not tree.tree_root.has_node(action):action="idle"
	var local: float = maxf(0.0,t-float(cue.get("start",0.0)))
	if action!=current_state:
		if last_time<0.0 and local>0.2:playback.start(action)
		else:playback.travel(action)
		current_state=action
	for key in bones:
		bones[key].position=rest[key]
		bones[key].rotation=0.0
	for clip in clip_names:tree.set("parameters/"+clip+"/Clock/seek_request",fposmod(t,2.0))
	tree.advance(maxf(0.0,t-last_time) if last_time>=0.0 else 0.0)
	last_time=t
	var duration: float = maxf(0.01,float(cue.get("end",t+1.0))-float(cue.get("start",0.0)))
	var envelope := smooth01(local/0.22)*smooth01((duration-local)/0.24)
	var walking := action in ["walk","run","step_back","move_closer","move_away"]
	var speed: float = cue.get("speed",85.0 if action!="run" else 160.0)
	var stride := 65.0 if action!="run" else 92.0
	var frequency: float=maxf(0.15,absf(speed)/stride)
	var cycle := local*frequency
	var style:Dictionary=cue.get("motion",{})
	var distance:float=absf(float(cue.get("to_x",0.0))-float(cue.get("from_x",0.0)))
	if motion_version>=2:
		stride=float(style.get("stride",65.0))*(1.4 if action=="run" else 1.0)
		frequency=maxf(0.15,absf(speed)/(stride*base_scale))*float(style.get("tempo",1.0))
		cycle=distance*smooth01(local/duration)/(stride*base_scale) if distance>0.1 else local*frequency
	walk_phase=fposmod(cycle,1.0);walking_now=walking
	var shift := sin(t*1.7+float(identity.hash()%31))*0.8
	if walking: shift = -3.0*absf(sin(cycle*TAU))*envelope
	if walking and motion_version>=2:
		# Contact -> down -> passing -> up. Travel phase follows eased root motion.
		var beat:float=fposmod(cycle*2.0,1.0)
		shift=(sin(beat*TAU)*float(style.get("bounce",2.5)))*envelope
		# Transfer weight over the stance leg, away from the swinging foot.
		bones.Hips.position.x-=sin(cycle*TAU)*2.0*envelope
		bones.Torso.rotation+=sin(cycle*TAU)*0.012*envelope
	bones.Hips.position.y += shift+((5.0 if motion_version>=2 else 12.0)*envelope if walking else 0.0)
	bones.Head.rotation = float(cue.get("gaze",0.0))*(0.12 if action in ["turn","look_around"] else 0.035)*envelope
	bones.Head.position.x += float(cue.get("gaze",0.0))*3.0*envelope
	var gesture := sin(local*3.0)*envelope
	if action in ["talk","explain"]:
		bones.RightUpperArm.rotation = -0.28*envelope-0.10*gesture
		bones.RightForearm.rotation = -0.55*envelope+0.12*gesture
	elif action in ["point","raise_hand","wave","celebrate"]:
		bones.RightUpperArm.rotation=-1.2*envelope
		bones.RightForearm.rotation=(-0.6+(0.35*sin(local*7.0) if action=="wave" else 0.0))*envelope
		if action=="celebrate":bones.LeftUpperArm.rotation=1.3*envelope
	elif action in ["fear","confused","scratch_head","touch_chin","fold_arms"]:
		bones.RightUpperArm.rotation=-0.5*envelope
		bones.RightForearm.rotation=-1.3*envelope
		bones.LeftUpperArm.rotation=0.25*envelope
		if action=="fold_arms":bones.LeftForearm.rotation=1.1*envelope
	if walking:
		var swing:float=float(style.get("arm_swing",0.25)) if motion_version>=2 else 0.25
		bones.LeftUpperArm.rotation = -sin(cycle*TAU)*swing*envelope
		bones.RightUpperArm.rotation = sin(cycle*TAU)*swing*envelope
		bones.LeftForearm.rotation = -0.1-0.15*absf(sin(cycle*TAU))*envelope
		bones.RightForearm.rotation = 0.1+0.15*absf(sin(cycle*TAU))*envelope
	var feet_y := float(data.feet[1])-34.0
	for index in range(2):
		var side: String = "Left" if index==0 else "Right"
		var hip: Vector2 = Vector2(data.bones[side+"Thigh"].position[0],data.bones[side+"Thigh"].position[1])
		var phase := fposmod(cycle+index*0.5,1.0)
		var offset := 0.0
		var lift := 0.0
		if walking:
			if phase<0.6:offset=lerpf(stride*0.5,-stride*0.5,phase/0.6)
			else:
				var p := (phase-0.6)/0.4
				offset=lerpf(-stride*0.5,stride*0.5,smooth01(p))
				lift=sin(p*PI)*(26.0 if action!="run" else 46.0)
			offset*=envelope
			lift*=envelope
		var target := skeleton.to_global(Vector2(hip.x+offset,feet_y-lift))
		if walking:
			var plant_local: float=(floorf(cycle+index*0.5)-index*0.5)/frequency
			var next_local: float=plant_local+1.0/frequency
			if motion_version>=2 and distance>0.1:
				plant_local=inverse_smooth((floorf(cycle+index*0.5)-index*0.5)*stride*base_scale/distance)*duration
				next_local=inverse_smooth((floorf(cycle+index*0.5)-index*0.5+1.0)*stride*base_scale/distance)*duration
			var planted_x: float=root_x_at(plant_local,cue)+(hip.x-data.feet[0])*base_scale
			var next_x: float=root_x_at(next_local,cue)+(hip.x-data.feet[0])*base_scale
			var foot_x: float=planted_x if phase<0.6 else lerpf(planted_x,next_x,smooth01((phase-0.6)/0.4))
			target=Vector2(foot_x,position.y-(34.0+lift)*base_scale)
		var bend:float=1.0 if index==0 else -1.0
		# Front-view knees bend away from the centre line, avoiding scissoring.
		if walking and motion_version>=2:bend=-bend
		solve_leg(side,target,bend)
	if action in ["sit","stand_up"]:
		var seated := envelope if action=="sit" else 1.0-envelope
		bones.Hips.position.y+=48.0*seated
		bones.LeftThigh.rotation=-1.0*seated;bones.RightThigh.rotation=-0.9*seated
		bones.LeftLeg.rotation=1.25*seated;bones.RightLeg.rotation=1.2*seated
	expression=cue.get("emotion","neutral")
	var blink := fposmod(t+float(identity.hash()%17)*0.19,3.8)<0.105
	sprites.eyes_open.visible=not blink
	sprites.eyes_closed.visible=blink
	if sprites.has("pupils"):
		sprites.pupils.visible=not blink
		sprites.pupils.position.x=data.parts.pupils.origin[0]-data.bones.Head.position[0]+float(cue.get("gaze",0.0))*2.4*envelope
	var expression_weight:float=smooth01((t-float(cue.get("emotion_started",cue.start)))/.18)
	if not walking:
		if expression=="fear":bones.Torso.rotation-=.055*expression_weight;bones.Head.rotation+=.04*expression_weight
		elif expression in ["curious","thinking","confused"]:bones.Head.rotation-=.055*expression_weight;bones.Torso.rotation+=.02*expression_weight
	sprites.brows.position.y = data.parts.brows.origin[1]-data.bones.Head.position[1] + (-4.0 if expression in ["fear","surprised","curious"] else 3.0 if expression in ["angry","sad"] else -1.5 if expression in ["happy","laugh"] else 0.0)*expression_weight
	sprites.brows.rotation = (0.04 if expression in ["worried","sad","confused"] else -0.04 if expression=="angry" else 0.0)*expression_weight
	sprites.eyes_open.scale.y=1.08 if expression in ["surprised","fear"] else 1.0
	for shape in "ABCDEFGHX":
		var sprite: Sprite2D = sprites["mouth_"+shape]
		sprite.visible=shape==mouth or shape==mouth_next
		sprite.modulate.a = 1.0-mouth_blend if shape==mouth else mouth_blend if shape==mouth_next else 1.0
