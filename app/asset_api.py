"""Typed endpoints for asset discovery, review, choices and preflight."""
from fastapi import APIRouter,HTTPException,Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from app.assets import AssetError
from app.review import ReviewInput,AnalysisOut,AssetOut,MappingInput,MappingConflict,analyze,save_mapping


class MappingOut(BaseModel):
    scope:str
    alias:str
    asset_id:str
    saved:bool


class RefreshOut(BaseModel):
    characters:int
    backgrounds:int


def asset_router(get_library):
    router=APIRouter()

    @router.get('/api/sounds')
    def sounds():
        import json
        from pathlib import Path
        data=json.loads((Path(__file__).resolve().parents[1]/'assets/sounds/library.json').read_text(encoding='utf-8'))
        return [{'id':key,'name':value['description'],'license':value['license']} for key,value in data['sounds'].items()]

    @router.get('/api/sounds/{sound_id}/audio')
    def sound_audio(sound_id:str):
        import json
        from pathlib import Path
        from app.assets import safe_path
        root=Path(__file__).resolve().parents[1]/'assets/sounds'
        library=json.loads((root/'library.json').read_text(encoding='utf-8'))['sounds']
        if sound_id not in library:raise HTTPException(404,'Sound not registered')
        return FileResponse(safe_path(root,library[sound_id]['file']),media_type='audio/wav')

    @router.get('/api/characters',response_model=list[AssetOut])
    def characters(search:str='',status:str='',age_group:str=''):
        return get_library().public('characters',search=search,status=status,age_group=age_group)

    @router.get('/api/backgrounds',response_model=list[AssetOut])
    def backgrounds(search:str='',status:str='',time_of_day:str=''):
        return get_library().public('backgrounds',search=search,status=status,time_of_day=time_of_day)

    @router.post('/api/assets/refresh',response_model=RefreshOut)
    def refresh():
        library=get_library().refresh(force=True)
        return {'characters':len(library.characters),'backgrounds':len(library.backgrounds)}

    @router.get('/api/assets/{kind}/{asset_id}/preview')
    def preview(kind:str,asset_id:str):
        try: return FileResponse(get_library().preview(kind,asset_id),media_type='image/png')
        except (AssetError,OSError,ValueError) as exc: raise HTTPException(404,str(exc)) from exc

    def review(payload,tools=False):
        try: return analyze(get_library(),payload,tools)[0]
        except (AssetError,ValueError) as exc:
            raise HTTPException(422,{'ready':False,'issues':[{'type':'review','source_text':'Selections','reason':'invalid_selection','message':str(exc)}]}) from exc

    @router.post('/api/analyze',response_model=AnalysisOut)
    def analyze_story(payload:ReviewInput): return review(payload)

    @router.post('/api/resolve',response_model=AnalysisOut)
    def resolve_story(payload:ReviewInput): return review(payload)

    @router.post('/api/preflight',response_model=AnalysisOut)
    def preflight(payload:ReviewInput): return review(payload,True)

    @router.post('/api/mappings',response_model=MappingOut)
    def mappings(payload:MappingInput):
        try: return save_mapping(get_library(),payload)
        except MappingConflict as exc: raise HTTPException(409,{'message':str(exc),'reason':exc.reason,'confirmation_required':True}) from exc
        except (AssetError,ValueError) as exc: raise HTTPException(422,str(exc)) from exc

    return router
