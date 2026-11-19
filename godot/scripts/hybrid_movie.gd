extends "res://scripts/movie.gd"
## Animated Skeleton2D -> transparent SubViewport -> Sprite3D, never a still PNG.
var world := Node3D.new()
var lens := Camera3D.new()
var cards: Dictionary = {}
var shadows: Dictionary = {}
var viewports: Dictionary = {}
var environment_nodes: Dictionary = {}
var ground_offsets:Dictionary={}
var camera_trace:FileAccess
var unit := 0.01
var rig_anchor := Vector2(256,640)

func material(color: Color) -> StandardMaterial3D:
	var result:=StandardMaterial3D.new()
	result.albedo_color=color
	result.roughness=1.0
	result.metallic_specular=0.0
	result.diffuse_mode=BaseMaterial3D.DIFFUSE_TOON
	return result

func shape(parent: Node3D, mesh: Mesh, position3: Vector3, color: Color) -> MeshInstance3D:
	var node:=MeshInstance3D.new();node.mesh=mesh;node.position=position3;node.material_override=material(color);parent.add_child(node)
	return node

func soft_shadow(parent: Node3D, size3: Vector2, opacity: float) -> MeshInstance3D:
	var mesh:=PlaneMesh.new();mesh.size=size3
	var node:=MeshInstance3D.new();node.mesh=mesh
	var shader:=Shader.new()
	shader.code="shader_type spatial; render_mode unshaded, blend_mix, depth_draw_never, cull_disabled; uniform float strength=0.2; void fragment(){float r=length((UV-vec2(0.5))*2.0);ALBEDO=vec3(0.07,0.10,0.05);ALPHA=(1.0-smoothstep(0.25,1.0,r))*strength;}"
	var mat:=ShaderMaterial.new();mat.shader=shader;mat.set_shader_parameter("strength",opacity);node.material_override=mat
	node.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF;parent.add_child(node);node.position.y=0.012
	return node

func build_environment(id: String, spec: Dictionary) -> void:
	var root:=Node3D.new();world.add_child(root);environment_nodes[id]=root
	var background:Dictionary=data.backgrounds[id]
	var backdrop:=Sprite3D.new();backdrop.texture=load_texture(background.file);backdrop.pixel_size=0.018
	var view_aspect:float=float(data.width)/float(data.height)
	var cover_width:float=2.0*(float(spec.camera.distance)+10.0)*tan(deg_to_rad(float(spec.camera.fov)/2.0))*view_aspect*1.12
	backdrop.pixel_size=maxf(0.018,cover_width/float(backdrop.texture.get_width()))
	backdrop.position=Vector3(0,float(backdrop.texture.get_height())*backdrop.pixel_size*0.293,-10);backdrop.shaded=false;backdrop.no_depth_test=false;root.add_child(backdrop)
	var art_shader:=Shader.new();art_shader.code="shader_type spatial; render_mode unshaded, cull_disabled, blend_mix, depth_draw_never; uniform sampler2D art: source_color; void fragment(){vec4 c=texture(art,UV);ALBEDO=c.rgb;ALPHA=c.a*(1.0-smoothstep(0.64,0.82,UV.y));}"
	var art_material:=ShaderMaterial.new();art_material.shader=art_shader;art_material.set_shader_parameter("art",backdrop.texture);backdrop.material_override=art_material
	var floor_mesh:=PlaneMesh.new();floor_mesh.size=Vector2(80,120)
	var floor3:=shape(root,floor_mesh,Vector3(0,0,-35),Color(spec.ground_color))
	if spec.get("kind","")=="station":floor3.position.y=-0.65
	var floor_mat:=material(Color.WHITE);floor_mat.albedo_texture=load_texture(background.file)
	floor_mat.uv1_scale=Vector3(0.26,0.09,1);floor_mat.uv1_offset=Vector3(0.38,0.83,0);floor3.material_override=floor_mat
	for part in spec.get("geometry",[]):
		var box:=BoxMesh.new();box.size=Vector3(part.size[0],part.size[1],part.size[2])
		var object3:=shape(root,box,Vector3(part.position[0],part.position[1],part.position[2]),Color(part.color))
		if part.get("unshaded",false):object3.material_override.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	for tree in spec.trees:
		var p:=Vector3(tree.position[0],0,tree.position[2]);var h:float=tree.height
		var trunk:=CylinderMesh.new();trunk.top_radius=0.15;trunk.bottom_radius=0.30;trunk.height=h;trunk.radial_segments=8;trunk.rings=1
		shape(root,trunk,p+Vector3(0,h/2,0),Color(spec.trunk_color))
		for i in range(3):
			var canopy:=SphereMesh.new();canopy.radius=float(tree.radius)*(0.9 if i>0 else 1.0);canopy.height=canopy.radius*1.35;canopy.radial_segments=10;canopy.rings=5
			var crown:=shape(root,canopy,p+Vector3((i-1)*0.65,h-0.2+float(i%2)*0.5,float(i-1)*0.3),Color(spec.leaf_color).lightened(i*0.055))
			var outline:=MeshInstance3D.new();outline.mesh=canopy;outline.scale=Vector3.ONE*1.018
			var ink:=material(Color("264525"));ink.cull_mode=BaseMaterial3D.CULL_FRONT;ink.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED;outline.material_override=ink;outline.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF;crown.add_child(outline)
		var tree_shadow:=soft_shadow(root,Vector2(tree.radius*2.2,tree.radius*1.1),0.16);tree_shadow.position+=p+Vector3(0.5,0,0.4)
	if background.get("foreground")!=null:
		var fg:=Sprite3D.new();fg.texture=load_texture(background.foreground);fg.pixel_size=0.018;fg.position=Vector3(0,7,-8.5);root.add_child(fg)

func _ready() -> void:
	camera.free() # Camera2D allocated by the base timing/subtitle helper is unused.
	var args:=OS.get_cmdline_user_args();data=JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	if not portrait_canvas():return
	add_child(world)
	if data.has("trace_file"):trace=FileAccess.open(data.trace_file,FileAccess.WRITE)
	camera_trace=FileAccess.open(data.trace_file.replace("-poses.jsonl","-camera.jsonl"),FileAccess.WRITE)
	var spec:Dictionary=data.hybrid_environments.values()[0]
	var env:=WorldEnvironment.new();var settings:=Environment.new();settings.background_mode=Environment.BG_COLOR;settings.background_color=Color(spec.sky_color)
	settings.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR;settings.ambient_light_color=Color("fff0d0");settings.ambient_light_energy=0.65
	settings.tonemap_mode=Environment.TONE_MAPPER_LINEAR;env.environment=settings;world.add_child(env)
	# Soft analytic contact shadows replace harsh low-resolution cascades.
	var sun:=DirectionalLight3D.new();sun.rotation_degrees=Vector3(-48,-30,0);sun.light_color=Color("fff0d2");sun.light_energy=0.85;sun.shadow_enabled=false;world.add_child(sun)
	for id in data.hybrid_environments:build_environment(id,data.hybrid_environments[id])
	for description in data.characters:
		var viewport:=SubViewport.new();viewport.size=Vector2i(512,768);viewport.transparent_bg=true;viewport.disable_3d=true;viewport.render_target_update_mode=SubViewport.UPDATE_ALWAYS;add_child(viewport)
		var rig=Rig.new();viewport.add_child(rig);rig.setup(description,0.8);rig.position=rig_anchor
		for child in rig.get_children():
			if child is Polygon2D:child.visible=false
		actors[description.id]=rig;viewports[description.id]=viewport
		var foot:Dictionary=description.rig.parts.left_foot
		ground_offsets[description.id]=(float(foot.origin[1])+float(foot.size[1])-float(description.rig.feet[1]))*0.8*unit
		var card:=Sprite3D.new();card.texture=viewport.get_texture();card.pixel_size=unit;card.shaded=false;card.texture_filter=BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
		card.billboard=BaseMaterial3D.BILLBOARD_DISABLED;card.position.y=(640-384)*unit;card.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF;world.add_child(card);cards[description.id]=card
		shadows[description.id]=soft_shadow(world,Vector2(1.55,0.65),0.25)
	world.add_child(lens);lens.current=true;lens.fov=spec.camera.fov;lens.near=0.1;lens.far=70
	var canvas:=CanvasLayer.new();add_child(canvas);canvas.add_child(caption)
	evaluate(float(data.start_frame)/data.fps)
	if data.get("capture_viewports",false):RenderingServer.frame_post_draw.connect(capture_rigs,CONNECT_ONE_SHOT)

func capture_rigs() -> void:
	var report:Dictionary={}
	for id in viewports:
		var image:Image=viewports[id].get_texture().get_image();var bounds:=image.get_used_rect()
		image.save_png(data.trace_file.get_base_dir()+"/"+id+"-viewport.png")
		report[id]={"corner_alpha":image.get_pixel(0,0).a,"bounds":[bounds.position.x,bounds.position.y,bounds.size.x,bounds.size.y],"size":[image.get_width(),image.get_height()]}
	var file:=FileAccess.open(data.trace_file.get_base_dir()+"/viewport-alpha.json",FileAccess.WRITE);file.store_string(JSON.stringify(report));file.close()

func camera_pose(scene: Dictionary, spec: Dictionary) -> Array:
	var focus:=Vector3(0,spec.camera.target_height,0);var distance:float=spec.camera.distance
	var shot:Dictionary=scene.camera;var target_id:String=str(shot.get("target",""))
	if cards.has(target_id) and shot.shot not in ["establishing","wide"]:
		focus.x=cards[target_id].position.x
		if shot.shot=="two_shot" and cards.has(shot.get("partner","")):focus.x=(focus.x+cards[shot.partner].position.x)/2.0
		distance*=0.80 if shot.shot=="two_shot" else 0.78 if shot.shot=="medium" else 0.70
		focus.y=3.15
	var position3:=Vector3(clampf(focus.x*0.15,-0.45,0.45),spec.camera.height,distance)
	return [position3,focus]

func evaluate(t: float) -> void:
	var scene:=interval(t);var spec:Dictionary=data.hybrid_environments[scene.background_id]
	for id in environment_nodes:environment_nodes[id].visible=id==scene.background_id
	update_caption(scene,t,data.width,data.height)
	var visible:Array=scene.visible_characters
	for id in actors:
		var rig=actors[id];var card:Sprite3D=cards[id];var present:bool=id in visible;card.visible=id in shot_participants(scene);shadows[id].visible=card.visible
		if not present:continue
		var cue:Dictionary=scene.actors[id];var index:int=visible.find(id)
		var phase:float=clampf((t-cue.start)/maxf(0.01,cue.end-cue.start),0,1);var offset:float=lerpf(cue.get("from_x",0.0),cue.get("to_x",0.0),smoothstep(0,1,phase))
		var placement:Dictionary=scene.spatial.actors[id]
		var origin:Vector3=Vector3(placement.position_from[0],0,placement.position_from[2]);var destination:Vector3=Vector3(placement.position_to[0],0,placement.position_to[2])
		var point:Vector3=origin.lerp(destination,smoothstep(0,1,phase));var x:float=point.x;var z:float=point.z
		var lift:float=ground_offsets[id]
		card.position=Vector3(x,(640-384)*unit+lift,z);shadows[id].position=Vector3(x,0.012,z)
		cue["base_x"]=rig_anchor.x-offset
		var mouth:Array=["X","",0.0]
		if id==scene.get("speaker","") and not scene.get("off_screen",true):mouth=mouth_value(scene.get("mouth_cues",[]),t-scene.start)
		rig.act(t,cue,mouth[0],mouth[1],mouth[2])
		if trace!=null and frame%3==0:
			var left:Vector2=rig.bones.LeftFoot.global_position;var right:Vector2=rig.bones.RightFoot.global_position
			var sole_l:Vector2=rig.sprites.left_foot.to_global(Vector2(rig.sprites.left_foot.texture.get_width()/2.0,rig.sprites.left_foot.texture.get_height()))
			var sole_r:Vector2=rig.sprites.right_foot.to_global(Vector2(rig.sprites.right_foot.texture.get_width()/2.0,rig.sprites.right_foot.texture.get_height()))
			trace.store_line(JSON.stringify({"frame":int(round(t*data.fps)),"character":id,"mouth":mouth[0],"walking":rig.walking_now,"walk_phase":rig.walk_phase,"root_3d":[x,0,z],"left_ankle_world":[x+(left.x-rig_anchor.x)*unit,(rig_anchor.y-left.y)*unit+lift,z],"right_ankle_world":[x+(right.x-rig_anchor.x)*unit,(rig_anchor.y-right.y)*unit+lift,z],"sole_heights":[(rig_anchor.y-sole_l.y)*unit+lift,(rig_anchor.y-sole_r.y)*unit+lift],"render_mode":"hybrid_2_5d","alpha_viewport":true,"head":rig.bones.Head.rotation,"elbow":rig.bones.RightForearm.rotation,"ground_y":0.0}))
	var desired:=camera_pose(scene,spec);var previous:=desired;var index_scene:int=data.direction.find(scene)
	if index_scene>0 and data.direction[index_scene-1].source_scene_id==scene.source_scene_id:previous=camera_pose(data.direction[index_scene-1],spec)
	var blend:float=smoothstep(0,1,clampf((t-scene.start)/0.6,0,1));lens.position=previous[0].lerp(desired[0],blend);lens.look_at(previous[1].lerp(desired[1],blend),Vector3.UP)
	# Keep the current shot's participants' heads inside the frame during pans.
	var participants:Array=shot_participants(scene)
	var look:Vector3=previous[1].lerp(desired[1],blend)
	for attempt in range(36):
		var fits:=true
		for id in participants:
			if not cards.has(id):continue
			var p:Vector3=cards[id].position
			for x_offset in [-0.95,0.95]:
				for y_head in [2.65,4.8]:
					var screen:Vector2=lens.unproject_position(Vector3(p.x+x_offset,y_head,p.z))
					var scale_ui:float=float(data.width)/720.0
					if screen.x<24*scale_ui or screen.x>float(data.width)-24*scale_ui or screen.y<24*scale_ui or screen.y>float(data.height)-160*scale_ui:fits=false
		if fits:break
		lens.position.z+=0.4;lens.look_at(look,Vector3.UP)
	if camera_trace!=null and frame%3==0:
		var bounds:Dictionary={}
		for id in participants:
			if not cards.has(id):continue
			var p:Vector3=cards[id].position;var box:=Rect2(lens.unproject_position(Vector3(p.x-0.95,4.8,p.z)),Vector2.ZERO)
			for dx in [-0.95,0.95]:
				for dy in [2.65,4.8]:box=box.expand(lens.unproject_position(Vector3(p.x+dx,dy,p.z)))
			bounds[id]=[box.position.x,box.position.y,box.end.x,box.end.y]
		camera_trace.store_line(JSON.stringify({"frame":int(round(t*data.fps)),"shot":scene.camera.shot,"camera":[lens.position.x,lens.position.y,lens.position.z],"subject_head_rects":bounds,"video_memory_bytes":Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED),"draw_calls":Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)}))
