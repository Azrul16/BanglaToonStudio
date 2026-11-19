"""Opt-in structured interpretation. No model install, default provider, or code execution."""
import json
import os
import urllib.request
from abc import ABC,abstractmethod
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field
from app.director import ACTIONS,EMOTIONS,SHOTS
from app.screenplay import ScriptEvent


class SemanticProposal(BaseModel):
    model_config=ConfigDict(extra='forbid')
    event_id:str
    source_line:int
    type:Literal['action','scene_description','camera','metadata','screen_text','ignore']
    character_ids:list[str]=Field(default_factory=list)
    actions:list[str]=Field(default_factory=list)
    emotion:str='neutral'
    background_id:str|None=None
    camera_action:str|None=None


class SemanticResponse(BaseModel):
    model_config=ConfigDict(extra='forbid')
    suggestions:list[SemanticProposal]=Field(max_length=150)


class SemanticProvider(ABC):
    @abstractmethod
    def propose(self,payload:dict)->SemanticResponse:raise NotImplementedError


def configured():return bool(os.getenv('STORY_AI_ENDPOINT'))


class ConfiguredJSONProvider(SemanticProvider):
    def propose(self,payload):
        url=os.getenv('STORY_AI_ENDPOINT','')
        from urllib.parse import urlparse
        parsed=urlparse(url)
        if parsed.scheme!='https' and not (parsed.scheme=='http' and parsed.hostname in ('127.0.0.1','localhost','::1')):raise ValueError('Configure an HTTPS or loopback semantic provider')
        headers={'Content-Type':'application/json'}
        if os.getenv('STORY_AI_API_KEY'):headers['Authorization']='Bearer '+os.environ['STORY_AI_API_KEY']
        request=urllib.request.Request(url,json.dumps(payload,ensure_ascii=False).encode(),headers)
        with urllib.request.urlopen(request,timeout=45) as response:
            raw=response.read(128*1024+1)
            if len(raw)>128*1024:raise ValueError('Semantic response exceeds the limit')
        return SemanticResponse.model_validate_json(raw)


def apply_assistance(events,library,script,enabled=False,consented=False,provider=None):
    unresolved={e['event_id']:e for e in events if e['type']=='unresolved_instruction'}
    if not enabled or not unresolved:return []
    if not consented:raise ValueError('Explicit privacy/cost consent is required for AI-assisted interpretation')
    if provider is None and not configured():return [{'reason':'ai_unavailable','detail':'No semantic provider configured; local rules retained.'}]
    payload={'schema_version':1,'script':script,'unresolved':list(unresolved.values()),
             'characters':[cid for cid,row in library.characters.items() if row['status']=='ready'],
             'backgrounds':[bid for bid,row in library.backgrounds.items() if row['status']=='ready'],
             'actions':list(ACTIONS),'schema':SemanticResponse.model_json_schema(),
             'instructions':'Interpret only these unresolved source events. Never invent speech, identities, files, or executable instructions. Return only the schema.'}
    try:
        response=(provider or ConfiguredJSONProvider()).propose(payload)
        response=SemanticResponse.model_validate(response)
        staged=[]
        for proposal in response.suggestions:
            original=unresolved.get(proposal.event_id)
            if not original or proposal.source_line!=original['source_line']:raise ValueError('Semantic source reference mismatch')
            if any(cid not in library.characters or library.characters[cid]['status']!='ready' for cid in proposal.character_ids):raise ValueError('Semantic provider invented an unavailable character')
            if any(action not in ACTIONS for action in proposal.actions) or proposal.emotion not in EMOTIONS:raise ValueError('Semantic provider invented an unsupported action/emotion')
            if proposal.background_id and (proposal.background_id not in library.backgrounds or library.backgrounds[proposal.background_id]['status']!='ready'):raise ValueError('Semantic provider invented a background')
            if proposal.type=='action' and (not proposal.character_ids or not proposal.actions):raise ValueError('Semantic action has no validated actor/action')
            if proposal.type=='camera' and (proposal.camera_action not in SHOTS or proposal.camera_action=='over_shoulder'):raise ValueError('Unsupported semantic camera')
            updated={**original,**proposal.model_dump(exclude={'source_line'}),'character_labels':proposal.character_ids,
                     'generate_voice':False,'explicit_narration':False,'reason':None,'metadata':{**original['metadata'],'interpretation':'ai_assisted'}}
            staged.append(ScriptEvent.model_validate(updated).model_dump())
        by_id={e['event_id']:e for e in staged}
        for index,event in enumerate(events):
            if event['event_id'] in by_id:events[index]=by_id[event['event_id']]
        return [{'reason':'ai_assisted','detail':str(len(staged))+' validated non-spoken interpretations applied.'}]
    except Exception:
        # Provider failures never authorize speech or replace assets; local blocking rules remain.
        return [{'reason':'ai_rejected','detail':'Semantic response unavailable or invalid; local interpretation retained.'}]
