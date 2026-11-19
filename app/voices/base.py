"""Backend-only provider contracts and bounded HTTP requests."""
import json
import urllib.request
import urllib.error
from pydantic import BaseModel,ConfigDict,model_serializer
from typing import Literal


class VoiceError(ValueError):pass


class VoiceIdentity(BaseModel):
    model_config=ConfigDict(extra='forbid')
    provider:Literal['vits','elevenlabs','azure','chatterbox_bangla']='vits'
    model:str='bangladeshi-vits'
    voice_id:str|None='default_bn'
    language:str='bn'
    reference_audio_hash:str|None=None
    model_revision:str|None=None
    generation_settings:dict|None=None
    synthesis_version:int|None=None
    category:str|None=None
    variation:dict|None=None
    usage_mode:str|None=None
    official_sample_id:str|None=None

    @model_serializer(mode='wrap')
    def compatibility(self,handler):
        data=handler(self)
        if self.provider!='chatterbox_bangla':
            for key in ('reference_audio_hash','model_revision','generation_settings','synthesis_version','category','variation','usage_mode','official_sample_id'):data.pop(key,None)
        return data


def fetch(url,headers,body=None,timeout=90):
    request=urllib.request.Request(url,data=body,headers=headers)
    try:
        with urllib.request.urlopen(request,timeout=timeout) as response:
            data=response.read(40*1024*1024+1)
            if len(data)>40*1024*1024:raise VoiceError('Provider returned an unexpectedly large audio response')
            return data,dict(response.headers)
    except urllib.error.HTTPError as exc:
        # Provider bodies can contain account details; do not echo them or keys.
        raise VoiceError(f'Voice provider returned HTTP {exc.code}. Check account access, quota and voice availability. No fallback was selected.') from None
    except (OSError,TimeoutError) as exc:raise VoiceError('Voice provider connection failed. No fallback was selected.') from None
