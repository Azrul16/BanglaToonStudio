"""Validated permanent assets. No runtime art creation or character substitution."""
import hashlib
import json
import math
import re
import unicodedata
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1] / 'assets'
ACTIONS = ('idle','blink','talk','walk','look_left','look_right','turn_head','surprised','afraid')
MOUTHS = 'ABCDEFGHX'


class AssetError(ValueError):
    pass


def read_json(path):
    try:
        value=json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(value,dict): raise ValueError('expected a JSON object')
        return value
    except (OSError, ValueError) as exc:
        raise AssetError(f'Missing or invalid asset metadata: {path.name}: {exc}') from exc


def normalize(value):
    value=unicodedata.normalize('NFC',value)
    # Copy/paste often inserts BOM/zero-width characters inside Bangla labels.
    value=''.join(c for c in value if unicodedata.category(c)!='Cf')
    return ' '.join(value.split()).casefold()


def registry(root=ROOT):
    value=read_json(root/'registry.json')
    if not isinstance(value.get('speakers'),dict) or not isinstance(value.get('locations'),dict):
        raise AssetError('Invalid speaker/location registry')
    return value


def speaker_info(label, root=ROOT):
    for character_id, entry in registry(root)['speakers'].items():
        if normalize(label) in {normalize(a) for a in [character_id, *entry['aliases']]}:
            if entry.get('requires_complete_rig'):
                load_character(character_id,root)
            return {'character_id':character_id, **entry}
    raise AssetError(f'Unknown speaker “{label}”. Add a registered character with a complete sprite rig; no substitute will be used.')


def mentions_alias(text,alias):
    alias=normalize(alias)
    def name_char(c): return c=='_' or unicodedata.category(c)[0] in 'LMN'
    for match in re.finditer(re.escape(alias),text):
        if match.start() and name_char(text[match.start()-1]): continue
        tail=''
        for c in text[match.end():]:
            if not name_char(c): break
            tail+=c
        if not tail or any('\u0980'<=c<='\u09ff' for c in alias) and tail in ('এর','ের','কে','রা','দের','ও','ই'):
            return True
    return False


def safe_path(directory, relative):
    path = (directory/relative).resolve()
    if not path.is_relative_to(directory.resolve()):
        raise AssetError('Asset path escapes its directory')
    return path


def validate_files(directory, metadata, required, alpha_required=True):
    hashes = metadata.get('file_hashes', {})
    if not isinstance(hashes,dict) or any(not isinstance(k,str) or not isinstance(v,str) or not re.fullmatch(r'[a-f0-9]{64}',v) for k,v in hashes.items()):
        raise AssetError('Invalid locked asset hashes')
    for filename in required:
        path=safe_path(directory,filename)
        if filename not in hashes or not path.is_file():
            raise AssetError(f'Missing locked asset {directory.name}/{filename}')
    for filename, expected in hashes.items():
        path=safe_path(directory,filename)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise AssetError(f'Asset identity mismatch: {directory.name}/{filename}. Restore the locked file or explicitly version a redesign.')
        if path.suffix.lower()=='.png':
            with Image.open(path) as im:
                im.load()
                if im.format!='PNG' or list(im.size)!=metadata['canvas']:
                    raise AssetError(f'Wrong PNG size or format: {filename}')
                if alpha_required or filename=='foreground.png':
                    if im.mode!='RGBA' or im.getchannel('A').getextrema()!=(0,255):
                        raise AssetError(f'Sprite must have visible artwork and transparent pixels: {filename}')
    identity = json.dumps({'version':metadata['version'],'hashes':hashes},sort_keys=True).encode()
    return hashlib.sha256(identity).hexdigest()


def load_character(character_id, root=ROOT):
    if not re.fullmatch(r'[a-z][a-z0-9_]*',character_id):
        raise AssetError('Invalid character ID')
    directory=root/'characters'/character_id
    meta=read_json(directory/'character.json')
    if not meta.get('animation_ready'):
        raise AssetError(f'{character_id} has design references only; a validated animation rig is required.')
    if meta.get('character_id')!=character_id or not re.fullmatch(r'\d+\.\d+\.\d+',meta.get('version','')):
        raise AssetError('Character ID/version mismatch')
    if meta.get('asset_version')!=meta['version'] or meta.get('rig_version')!=meta['version']:
        raise AssetError('Mixed character asset versions')
    if meta.get('voice_id')!='default_bn':
        raise AssetError('This single-speaker VITS model supports only the default_bn voice assignment')
    scale=meta.get('render_scale',1)
    if not isinstance(scale,(int,float)) or not math.isfinite(scale) or not .5<=scale<=1.2:
        raise AssetError('Invalid character render scale')
    if len(meta.get('canvas',[]))!=2 or any(not isinstance(n,int) or n<32 or n>2048 for n in meta['canvas']):
        raise AssetError('Invalid sprite canvas')
    for anchor in ('head','eyes','mouth','feet','left_arm','right_arm','left_leg','right_leg'):
        point=meta.get('anchors',{}).get(anchor,[])
        if len(point)!=2 or any(not isinstance(n,(int,float)) or not math.isfinite(n) or n<0 or n>meta['canvas'][i] for i,n in enumerate(point)):
            raise AssetError(f'Invalid character anchor: {anchor}')
    required=['body.png','head.png','hair.png','eyes/open.png','eyes/closed.png',
              *[f'mouths/{m}.png' for m in MOUTHS],*[f'{part}/{side}.png' for part in ('arms','legs') for side in ('left','right')],
              *[f'animations/{a}.json' for a in ACTIONS]]
    identity=validate_files(directory,meta,required)
    animations={}
    for action in ACTIONS:
        animation=read_json(directory/f'animations/{action}.json')
        frames=animation.get('keyframes',[])
        if animation.get('version')!=meta['version'] or animation.get('action')!=action or not isinstance(animation.get('duration'),(int,float)) or not 0<animation['duration']<=30:
            raise AssetError(f'Invalid animation version/duration: {action}')
        if len(frames)<2 or frames[0].get('t')!=0 or frames[-1].get('t')!=1:
            raise AssetError(f'Invalid animation boundaries: {action}')
        previous=-1
        for frame in frames:
            if not all(isinstance(frame.get(k),(int,float)) and math.isfinite(frame[k]) for k in ('t','x','y','head_angle')) or not previous<frame['t']<=1:
                raise AssetError(f'Invalid animation keyframes: {action}')
            previous=frame['t']
        animations[action]=animation
    return {**meta,'directory':directory,'identity_hash':identity,'animations':animations}


def load_background(background_id, root=ROOT):
    if not re.fullmatch(r'[a-z][a-z0-9_]*',background_id):
        raise AssetError('Invalid background ID')
    directory=root/'backgrounds'/background_id
    meta=read_json(directory/'metadata.json')
    # Supplied flat background packs need no made-up foreground or lighting.
    # Adapt their actual metadata in memory, preserving source files and IDs.
    if not meta.get('file_hashes') and meta.get('id')==background_id:
        name=meta.get('background_file','background.png')
        path=safe_path(directory,name)
        try:
            with Image.open(path) as image:
                image.load(); canvas=list(image.size)
                if image.format!='PNG': raise AssetError('Background must be a PNG')
        except OSError as exc: raise AssetError(f'Unreadable background: {name}') from exc
        if meta.get('width',canvas[0])!=canvas[0] or meta.get('height',canvas[1])!=canvas[1]:
            raise AssetError('Background dimensions do not match metadata')
        meta={**meta,'background_id':background_id,'version':meta.get('version','1.0.0'),'canvas':canvas,
              'layer_mode':'flat','file_hashes':{name:hashlib.sha256(path.read_bytes()).hexdigest()}}
    if meta.get('background_id')!=background_id or not re.fullmatch(r'\d+\.\d+\.\d+',meta.get('version','')):
        raise AssetError('Background ID/version mismatch')
    if len(meta.get('canvas',[]))!=2 or any(not isinstance(n,int) or n<64 or n>4096 for n in meta['canvas']):
        raise AssetError('Invalid background canvas')
    lamp=meta.get('lamp',[])
    if (lamp or meta.get('layer_mode')!='flat') and (len(lamp)!=2 or any(not isinstance(n,(int,float)) or not math.isfinite(n) or not 0<=n<=meta['canvas'][i] for i,n in enumerate(lamp))):
        raise AssetError('Invalid background lighting anchor')
    flat=meta.get('layer_mode')=='flat'
    if not flat and not lamp:
        raise AssetError('A layered background requires a lighting anchor')
    image_name=meta.get('background_file','background.png')
    identity=validate_files(directory,meta,[image_name] if flat else [image_name,meta.get('foreground_file','foreground.png')],False)
    return {**meta,'directory':directory,'identity_hash':identity}


def plan_story(parsed, root=ROOT):
    reg=registry(root)
    # Only narration establishes a location. Dialogue may mention other places.
    narration=' '.join(s['text'] for s in parsed.get('events',parsed['segments']) if s.get('type',s.get('kind'))!='dialogue')
    normalized=normalize(narration)
    unsupported=[w for w in reg['unsupported_locations'] if re.search(r'(?<![\w])'+re.escape(normalize(w))+r'(?![\w])',normalized)]
    if unsupported:
        raise AssetError(f'Unsupported scene: {unsupported[0]}. Only the saved rural railway station is available.')
    location=next((key for key,words in reg['locations'].items() if any(normalize(w) in normalized for w in words)),None)
    warnings=[]
    if not location:
        # Conservatively reject ambiguous narrative settings. Dialogue-only
        # stories may use the page's documented default stage, with a warning.
        if narration.strip():
            raise AssetError('No supported scene identified. Include রেলস্টেশন in the narration; only the saved railway-station background is currently available.')
        location='railway_station_night'
        warnings.append('No location identified; using the documented railway-station stage.')
    characters={}
    for segment in parsed['segments']:
        if not segment['off_screen']:
            cid=segment['speaker']
            characters[cid]=load_character(cid,root)
    # A named protagonist in narration is visible even with only off-screen speech.
    for cid,entry in reg['speakers'].items():
        if cid not in characters and not entry['off_screen'] and any(mentions_alias(normalized,a) for a in entry['aliases']):
            characters[cid]=load_character(cid,root)
    return {'background':load_background(location,root),'characters':characters,'warnings':warnings}


def asset_references(plan):
    backgrounds=plan.get('backgrounds',{plan['background']['background_id']:plan['background']})
    return {'characters':[{k:c[k] for k in ('character_id','version','voice_id','identity_hash','file_hashes')} for c in plan['characters'].values()],
            'background':{k:plan['background'][k] for k in ('background_id','version','identity_hash','file_hashes')},
            'backgrounds':[{k:b[k] for k in ('background_id','version','identity_hash','file_hashes')} for b in backgrounds.values()],
            'scenes':plan.get('review_scenes',[])}
