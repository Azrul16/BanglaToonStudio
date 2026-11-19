"""Discovered, validated local assets and safe cached preview images."""
import hashlib
import json
import json
import re
import threading
from pathlib import Path
from PIL import Image,ImageOps
from app.assets import ROOT,AssetError,load_character,load_background,normalize,read_json,safe_path

ID_RE=re.compile(r'[a-z][a-z0-9_]*')


class AssetLibrary:
    def __init__(self,root=ROOT,storage=None):
        self.root=Path(root)
        self.storage=Path(storage or self.root.parent/'workspace')
        self.lock=threading.RLock()
        self.signature=None
        self.characters={}; self.backgrounds={}

    def _signature(self):
        signature=[]
        for area in ('characters','backgrounds'):
            for path in sorted((self.root/area).rglob('*')):
                try:
                    if path.is_file() and path.suffix.lower() in ('.json','.png','.jpg','.jpeg'):
                        stat=path.stat();signature.append((str(path.relative_to(self.root)),stat.st_mtime_ns,stat.st_size))
                except OSError: continue
        try:
            stat=(self.root/'registry.json').stat();signature.append(('registry',stat.st_mtime_ns,stat.st_size))
        except OSError: pass
        return tuple(signature)

    def refresh(self,force=False):
        with self.lock:
            signature=self._signature()
            if not force and signature==self.signature: return self
            aliases={}
            try: aliases=read_json(self.root/'registry.json').get('speakers',{})
            except AssetError: pass
            characters={}; backgrounds={}
            for kind,target in (('characters',characters),('backgrounds',backgrounds)):
                base=self.root/kind
                if not base.is_dir(): continue
                for directory in sorted(base.iterdir()):
                    if not directory.is_dir() or not directory.resolve().is_relative_to(base.resolve()) or not ID_RE.fullmatch(directory.name): continue
                    filename='character.json' if kind=='characters' else 'metadata.json'
                    if not (directory/filename).exists() and not any(directory.glob('*.png')): continue
                    cid=directory.name
                    meta={}; bundle=None; reason=None
                    try:
                        meta=read_json(directory/filename)
                        bundle=load_character(cid,self.root) if kind=='characters' else load_background(cid,self.root)
                        status='ready'
                    except (AssetError,OSError,ValueError,KeyError,TypeError) as exc:
                        reason=str(exc)
                        has_rig=any((directory/name).exists() for name in ('body.png','head.png','hair.png')) or (directory/'mouths').is_dir()
                        reference=kind=='characters' and not has_rig and any(directory.glob('*sheet.png'))
                        status='reference_only' if reference else 'incomplete'
                    def text(value,default=''): return value if isinstance(value,str) else default
                    def strings(value): return [v for v in value if isinstance(v,str)] if isinstance(value,list) else []
                    if meta.get('aliases') is not None and not isinstance(meta['aliases'],list):
                        status='incomplete';reason='Asset aliases must be a list of names'
                    names=[cid,text(meta.get('name_bn')),text(meta.get('name_en')),*strings(meta.get('aliases',[]))]
                    if kind=='characters': names+=aliases.get(cid,{}).get('aliases',[])
                    else: names+=[*strings(meta.get('keywords_bn',[])),*strings(meta.get('keywords',[]))]
                    names=list(dict.fromkeys(n for n in names if isinstance(n,str) and n.strip()))
                    preview=None
                    for name in ([meta.get('preview_image'),'portrait_reference.png','character_sheet.png'] if kind=='characters'
                                 else [meta.get('preview_image'),meta.get('shorts_file'),meta.get('background_file'),'background.png']):
                        if not name: continue
                        try:
                            path=safe_path(directory,name)
                            with Image.open(path) as image: image.verify()
                            preview=path; break
                        except (OSError,ValueError,TypeError): continue
                    if kind=='characters' and status=='ready': preview='rig'
                    row={'id':cid,'character_id' if kind=='characters' else 'background_id':cid,
                         'name_bn':text(meta.get('name_bn'),cid),'name_en':text(meta.get('name_en'),cid.replace('_',' ').title()),
                         'aliases':names,'status':status,'reason':reason,'version':meta.get('version',meta.get('asset_version')),
                         'preview_url':f'/api/assets/{kind}/{cid}/preview' if preview else None,
                         'identity_hash':bundle['identity_hash'] if bundle else None,
                         '_bundle':bundle,'_preview':preview,'_directory':directory,'_meta':meta}
                    if kind=='characters':
                        age=meta.get('age')
                        row.update(age_group=meta.get('age_group','child' if isinstance(age,(int,float)) and age<18 else 'unspecified'),gender=meta.get('gender','unspecified'),voice_id=meta.get('voice_id','default_bn'))
                        row['articulated_status']='not_prepared'
                        row['articulated_note']='A design sheet or legacy rig is not a completed multi-view animation rig.'
                        if bundle and (directory/'articulated/v1/rig.json').is_file():
                            try:
                                from app.rendering.godot_adapter import rig_description
                                derived=rig_description(bundle)['rig']
                                row.update(articulated_status=derived['quality_status'],articulated_version=derived['version'],
                                           articulated_note='Jointed front-art prototype; profile/back artwork and alternate hand silhouettes are not ready.')
                            except (ValueError,OSError,KeyError) as exc:row.update(articulated_status='invalid',articulated_note=str(exc))
                    else:
                        canvas=bundle['canvas'] if bundle else [meta.get('width'),meta.get('height')]
                        row.update(time_of_day=meta.get('time_of_day',meta.get('lighting','unspecified')),resolution=canvas,
                                   aspect_ratio=round(canvas[0]/canvas[1],4) if all(isinstance(n,int) and n>0 for n in canvas) else None,
                                   family_id=meta.get('variant_source') or cid)
                    target[cid]=row
            self.characters,self.backgrounds=characters,backgrounds
            self.signature=signature
        return self

    def public(self,kind,search='',status='',age_group='',time_of_day=''):
        self.refresh()
        rows=self.characters if kind=='characters' else self.backgrounds
        query=normalize(search)
        return [{k:v for k,v in row.items() if not k.startswith('_')} for row in rows.values()
                if (not query or query in normalize(' '.join(row['aliases']))) and (not status or row['status']==status)
                and (not age_group or row.get('age_group')==age_group) and (not time_of_day or row.get('time_of_day')==time_of_day)]

    def preview(self,kind,cid):
        if kind not in ('characters','backgrounds') or not ID_RE.fullmatch(cid): raise AssetError('Invalid preview ID')
        self.refresh()
        rows=self.characters if kind=='characters' else self.backgrounds
        row=rows.get(cid)
        if not row or not row['_preview']: raise AssetError('Preview unavailable for this asset')
        source=row['_preview']
        fingerprint=row['identity_hash'] or str(source.stat().st_mtime_ns)+str(source.stat().st_size)
        key=hashlib.sha256(f'{kind}:{cid}:{fingerprint}:{json.dumps(row["_meta"],sort_keys=True)}'.encode()).hexdigest()
        target=self.storage/'thumbnails'/f'{key}.png'
        with self.lock:
            if target.exists(): return target
            target.parent.mkdir(parents=True,exist_ok=True)
            if source=='rig':
                from app.engines.animation import compose_character
                image,_=compose_character(row['_bundle'],1,'idle')
                image=image.crop(image.getbbox())
            else:
                with Image.open(source) as original: image=original.convert('RGBA')
            image=ImageOps.contain(image,(240,300),Image.Resampling.LANCZOS)
            tile=Image.new('RGBA',(240,300),'#edf0ee')
            tile.alpha_composite(image,((240-image.width)//2,(300-image.height)//2))
            temporary=target.with_suffix('.tmp')
            tile.convert('RGB').save(temporary,format='PNG'); temporary.replace(target)
        return target
