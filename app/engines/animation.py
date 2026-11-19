"""CPU sprite compositor: locked PNG layers, keyframes and a shared camera."""
import math
import os
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, features
from app.engines import text_layout
from app.video_config import VIDEO_WIDTH,VIDEO_HEIGHT

ROOT=Path(__file__).resolve().parents[2]
SIZE=(VIDEO_WIDTH,VIDEO_HEIGHT)
LEGACY_ACTIONS={'stop':'idle','turn':'turn_head','fear':'afraid','look_around':'look_left'}


@lru_cache(maxsize=12)
def font(size=28):
    path=Path(os.getenv('TOON_FONT',str(ROOT/'assets/fonts/NotoSansBengali.ttf')))
    if not path.is_file(): raise RuntimeError('Bengali font missing; restore assets/fonts/NotoSansBengali.ttf')
    return ImageFont.truetype(str(path),size)


def text(image,xy,value,size,fill,anchor=None):
    face=font(size)
    if features.check_feature('raqm'):
        ImageDraw.Draw(image).multiline_text(xy,value,font=face,fill=fill,anchor=anchor,spacing=10)
    else:
        text_layout.draw_text(image,xy,value,face,fill,anchor,spacing=10)


def width(value,face):
    return face.getlength(value) if features.check_feature('raqm') else text_layout.length(value,face)


def interpolate(animation,time):
    phase=time/animation['duration']
    phase=phase%1 if animation['loop'] else min(1,max(0,phase))
    frames=animation['keyframes']
    for left,right in zip(frames,frames[1:]):
        if phase<=right['t']:
            t=max(0,(phase-left['t'])/(right['t']-left['t']))
            t=t*t*(3-2*t)
            return {k:left[k]+(right[k]-left[k])*t for k in ('x','y','head_angle')}
    return {k:frames[-1][k] for k in ('x','y','head_angle')}


@lru_cache(maxsize=40)
def sprite(path,identity):
    with Image.open(path) as im: return im.convert('RGBA')


@lru_cache(maxsize=24)
def head_sprite(directory,identity,mouth,eyes,has_back=False,canvas=(384,640)):
    result=Image.new('RGBA',canvas)
    back=Path(directory)/'hair_back.png'
    if has_back: result.alpha_composite(sprite(str(back),identity))
    for name in ('head.png','hair.png',f'eyes/{eyes}.png',f'mouths/{mouth}.png'):
        result.alpha_composite(sprite(str(Path(directory)/name),identity))
    return result


def rotate_layer(image,pivot,angle):
    """Transform only the occupied sprite rectangle, retaining world anchors."""
    bounds=image.getbbox()
    cropped=image.crop(bounds)
    if not angle: return cropped,(bounds[0],bounds[1])
    cosine=math.cos(math.radians(angle)); sine=math.sin(math.radians(angle))
    px,py=pivot
    corners=[(px+cosine*(x-px)+sine*(y-py),py-sine*(x-px)+cosine*(y-py))
             for x,y in ((bounds[0],bounds[1]),(bounds[2],bounds[1]),(bounds[2],bounds[3]),(bounds[0],bounds[3]))]
    left=math.floor(min(x for x,y in corners))-2; top=math.floor(min(y for x,y in corners))-2
    right=math.ceil(max(x for x,y in corners))+2; bottom=math.ceil(max(y for x,y in corners))+2
    matrix=(cosine,-sine,px+cosine*(left-px)-sine*(top-py)-bounds[0],
            sine,cosine,py+sine*(left-px)+cosine*(top-py)-bounds[1])
    return cropped.transform((right-left,bottom-top),Image.Transform.AFFINE,matrix,Image.Resampling.BICUBIC),(left,top)


@lru_cache(maxsize=96)
def limb_sprite(path,identity,pivot,angle):
    return rotate_layer(sprite(path,identity),pivot,angle)


@lru_cache(maxsize=48)
def rotated_head(directory,identity,mouth,eyes,pivot,angle,has_back=False,canvas=(384,640)):
    return rotate_layer(head_sprite(directory,identity,mouth,eyes,has_back,canvas),pivot,angle)


def compose_character(character,time,action='idle',mouth='X',action_time=None,previous_action='idle',expression_mouth=True):
    directory=character['directory']; identity=character['identity_hash']
    anchors=character['anchors']
    animation=character['animations'][action]
    pose=interpolate(animation,time if action_time is None else action_time)
    if action_time is not None and action_time<.25:
        prior=character['animations'][previous_action]
        previous=interpolate(prior,prior['duration']-.0001)
        blend=max(0,action_time/.25); blend=blend*blend*(3-2*blend)
        for key in pose: pose[key]=previous[key]*(1-blend)+pose[key]*blend
    rig=Image.new('RGBA',tuple(character['canvas']))
    walking=action=='walk'
    cycle=math.sin(time*8)
    for side,sign in (('left',1),('right',-1)):
        angle=round(sign*cycle*15*2)/2 if walking else 0
        leg,position=limb_sprite(str(directory/f'legs/{side}.png'),identity,tuple(anchors[f'{side}_leg']),angle)
        rig.alpha_composite(leg,position)
    for side,sign in (('left',1),('right',-1)):
        angle=sign*cycle*11 if walking else math.sin(time*1.8)*2
        if action=='afraid': angle+=sign*12
        arm,position=limb_sprite(str(directory/f'arms/{side}.png'),identity,tuple(anchors[f'{side}_arm']),round(angle*2)/2)
        rig.alpha_composite(arm,position)
    rig.alpha_composite(sprite(str(directory/'body.png'),identity))
    eyes='closed' if time%4.1<.14 or action=='blink' else 'open'
    if action=='surprised' and mouth=='X' and expression_mouth: mouth='D'
    angle=pose['head_angle']
    if action=='afraid': angle+=math.sin(time*7)*1.5
    head,position=rotated_head(str(directory),identity,mouth,eyes,tuple(anchors['head']),round(angle*2)/2,'hair_back.png' in character['file_hashes'],tuple(character['canvas']))
    rig.alpha_composite(head,position)
    return rig,pose


@lru_cache(maxsize=1)
def fog_tile():
    fog=Image.new('RGBA',(1100,280))
    d=ImageDraw.Draw(fog)
    for x,y,w in [(30,100,430),(330,30,500),(680,90,370)]:
        d.ellipse((x,y,x+w,y+100),fill=(179,198,196,18))
    return fog.filter(ImageFilter.GaussianBlur(26))


@lru_cache(maxsize=16)
def lamp_tile(strength):
    light=Image.new('RGBA',(250,300))
    ImageDraw.Draw(light).ellipse((30,30,220,250),fill=(250,213,145,strength))
    return light.filter(ImageFilter.GaussianBlur(26))


@lru_cache(maxsize=3)
def stage_background(path,identity,size=(900,1500)):
    return ImageOps.fit(sprite(path,identity),size,method=Image.Resampling.LANCZOS)


def character_layout(character,index,count,stage_size=(900,1500)):
    width,height=character['canvas']
    if stage_size[0]>stage_size[1]:
        scale=min(520/height,(1400/max(1,count)-24)/width)*character.get('render_scale',1.)
        return 800+(index-(count-1)/2)*(1400/max(1,count)),750,max(.01,scale)
    scale=(min(.93*640/height,580/width) if count==1 else min(.74*640/height,(750/count-20)/width))*character.get('render_scale',1.)
    x=510 if count==1 else 450+(index-(count-1)/2)*(750/count)
    return x,1120,scale


def render_scene(scene:dict,assets_dir=None,output_path=None):
    plan=scene['plan']; background=plan.get('backgrounds',{}).get(scene.get('background_id'),plan['background']); t=scene['time']
    identity=background['identity_hash']; directory=background['directory']
    from app.video_config import validate_canvas
    size=tuple(scene.get('output_size',SIZE));validate_canvas(*size)
    stage_size=(900,1500)
    world=stage_background(str(directory/background.get('background_file','background.png')),identity,stage_size).copy()
    # Subtle dim-light variation and fog. These overlays never change asset art.
    strength=round(13+4*math.sin(t*2.1)+2*math.sin(t*5.7))
    if background.get('lamp'):
        lx,ly=background['lamp'];lx=round(lx*stage_size[0]/900);ly=round(ly*stage_size[1]/1500)
        world.alpha_composite(lamp_tile(strength),(lx-125,ly-90))
    for index,cid in enumerate(scene['visible_characters']):
        character=plan['characters'][cid]
        active=scene.get('speaker')==cid and not scene.get('off_screen',True)
        action=scene.get('action','idle')
        instruction=scene.get('instruction')
        if instruction and scene.get('kind')=='action' and cid not in instruction['character_ids']:action='idle'
        action=LEGACY_ACTIONS.get(action,action)
        if action=='talk' and not active: action='idle'
        mouth=scene.get('mouth','X') if active else 'X'
        previous=LEGACY_ACTIONS.get(scene.get('previous_action'),scene.get('previous_action','idle'))
        rig,pose=compose_character(character,t,action,mouth,scene.get('local_time',0),previous,
                                   expression_mouth=scene.get('kind')!='speech' or active)
        x,y,scale=character_layout(character,index,len(scene['visible_characters']),stage_size)
        rig_size=tuple(round(n*scale) for n in rig.size)
        rig=rig.resize(rig_size,Image.Resampling.LANCZOS)
        feet=character['anchors']['feet']
        world.alpha_composite(rig,(round(x-feet[0]*scale+pose['x']),round(y-feet[1]*scale+pose['y'])))
    foreground=background.get('foreground_file','foreground.png')
    if foreground in background['file_hashes']:
        layer=ImageOps.fit(sprite(str(directory/foreground),identity),stage_size,method=Image.Resampling.LANCZOS)
        world.alpha_composite(layer,(round(math.sin(t*.17)*3),0))
    if background.get('time_of_day',background.get('lighting')) in ('night','misty','dusk'):
        world.alpha_composite(fog_tile(),(round(-100+math.sin(t*.13)*60),970))
    # One continuous camera across every segment and hold prevents hard cuts.
    zoom=1.015+.025*min(1,t/max(1,scene['total_duration']))
    crop_h=world.height/zoom; crop_w=crop_h*size[0]/size[1]
    cx=world.width/2+math.sin(t*.12)*14; cy=world.height/2
    left=max(0,min(world.width-crop_w,cx-crop_w/2))
    top=max(0,min(world.height-crop_h,cy-crop_h/2))
    image=world.convert('RGB').crop((round(left),round(top),round(left+crop_w),round(top+crop_h))).resize(size,Image.Resampling.BICUBIC)
    cue=scene.get('subtitle') or scene.get('screen_text_asset')
    if cue and cue['start']<=t<cue['end']:
        from app.subtitles import bitmap
        layer,settings=bitmap(cue['text'],*size)
        surface=image.convert('RGBA');surface.alpha_composite(layer,(0,size[1]-settings['bottom_margin']-layer.height));image=surface.convert('RGB')
    elif scene.get('caption') and not cue:
        from app.subtitles import bitmap
        layer,settings=bitmap(scene['caption'],*size)
        surface=image.convert('RGBA');surface.alpha_composite(layer,(0,size[1]-settings['bottom_margin']-layer.height));image=surface.convert('RGB')
    elif scene.get('kind')=='intro':
        title=background.get('name_bn',background.get('name',''))
        text(image,(55,size[1]-150),title,30,'#eae6ce')
    if output_path: image.save(output_path)
    return image
