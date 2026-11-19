"""Shaped Bengali full-take subtitles, timed from actual approved WAVs.

No character-count page timing or fabricated word alignment. Long speech is
chunked before synthesis, so each subtitle still follows a real audio take.
"""
from functools import lru_cache
from pathlib import Path
from PIL import Image,ImageFilter
from app.scene_cache import fingerprint
from app.engines import text_layout

STYLE_VERSION=3


def layout(value,width,height):
    from app.engines.animation import font,width as measure
    margin=round(width*.075)
    maximum=width-margin*2
    from app.video_config import validate_canvas
    validate_canvas(width,height)
    scale=width/720
    for size in range(round(48*scale),round(28*scale)-1,-1):
        face=font(size);lines=[];line=''
        for word in value.split():
            candidate=(line+' '+word).strip()
            if line and measure(candidate,face)>maximum:lines.append(line);line=word
            else:line=candidate
        if line:lines.append(line)
        if len(lines)<=2 and all(measure(row,face)<=maximum for row in lines):
            return {'lines':lines,'font_size':size,'margin':margin,'bottom_margin':round(height*.12),'max_lines':2,'style_version':STYLE_VERSION}
    raise ValueError('Dialogue is too long for readable two-line subtitles; split this spoken sentence into shorter takes.')


@lru_cache(maxsize=256)
def bitmap(value,width,height):
    from app.engines.animation import font
    settings=layout(value,width,height);face=font(settings['font_size']);size=face.size
    layers=[]
    for line in settings['lines']:
        layer,_=text_layout.text_layer(line,face.path,size,'#ffffff')
        box=layer.getbbox()
        if box:layers.append(layer.crop(box))
    line_height=round(size*1.5);canvas=Image.new('RGBA',(width,max(1,len(layers))*line_height+16))
    for i,layer in enumerate(layers):canvas.alpha_composite(layer,(round((width-layer.width)/2),8+i*line_height))
    # Slightly strengthen the shaped glyph mask for a medium-bold appearance.
    mask=canvas.getchannel('A').filter(ImageFilter.MaxFilter(3))
    shadow=Image.new('RGBA',canvas.size,(0,0,0,0));blur=mask.filter(ImageFilter.GaussianBlur(1.2))
    shadow.paste(Image.new('RGBA',canvas.size,(0,0,0,100)),(2,2),blur)
    outline=Image.new('RGBA',canvas.size,(12,14,18,255));outline.putalpha(mask.filter(ImageFilter.MaxFilter(3)))
    ink=Image.new('RGBA',canvas.size,'white');ink.putalpha(mask)
    shadow.alpha_composite(outline);shadow.alpha_composite(ink)
    return shadow,settings


def prepare(timeline,directory):
    folder=directory/'render/subtitles';folder.mkdir(parents=True,exist_ok=True)
    track=[]
    for scene in timeline['scenes']:
        if scene['kind'] not in ('speech','screen_text'):continue
        value=scene.get('text','') if scene['kind']=='speech' else scene.get('screen_text','')
        if not value:continue
        image,settings=bitmap(value,timeline['width'],timeline['height'])
        key=fingerprint({'text':value,'width':timeline['width'],'height':timeline['height'],'style':STYLE_VERSION})
        path=folder/(key+'.png')
        if not path.is_file():image.save(path)
        cue={'text':value,'start':scene['start'],'end':scene['start']+scene['audio_duration'] if scene['kind']=='speech' else scene['end'],
            'file':str(path.resolve()).replace('\\','/'),'image_height':image.height,**settings,'alignment':'full_approved_take','speaker_prefix':False,'background_box':False}
        scene['subtitle' if scene['kind']=='speech' else 'screen_text_asset']=cue
        if scene['kind']=='speech':track.append(cue)
    timeline['subtitles']=track
    return track
