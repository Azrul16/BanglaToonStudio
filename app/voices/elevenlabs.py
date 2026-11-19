"""Official Text to Dialogue API; IDs come from this account's actual catalog."""
import json
import os
from urllib.parse import urlencode
from app.voices.base import VoiceError,fetch

TAGS={'happy':'[happy]','fear':'[scared]','surprised':'[surprised]','curious':'[curious]','sad':'[sad]','laugh':'[laughs]','whisper':'[whispers]',
      'excited':'[excited]','confused':'[confused]','angry':'[angry]','thinking':'[thoughtful]','cry':'[crying]'}


def headers():
    key=os.getenv('ELEVENLABS_API_KEY')
    if not key:raise VoiceError('Set ELEVENLABS_API_KEY in the server environment to use ElevenLabs')
    return {'xi-api-key':key,'Content-Type':'application/json'}


def voices():
    rows=[];token=None
    for _ in range(30):
        query={'page_size':100}
        if token:query['next_page_token']=token
        raw,_=fetch('https://api.elevenlabs.io/v2/voices?'+urlencode(query),headers(),timeout=30)
        data=json.loads(raw)
        for voice in data.get('voices',[]):
            rows.append({'voice_id':voice['voice_id'],'name':voice.get('name') or voice['voice_id'],'labels':voice.get('labels',{}),
                         'preview_available':bool(voice.get('preview_url')),'preview_url':voice.get('preview_url') if str(voice.get('preview_url','')).startswith('https://') else None,
                         'languages':voice.get('verified_languages',[]),'description':voice.get('description',''),'provider':'elevenlabs'})
        if not data.get('has_more'):return rows
        token=data.get('next_page_token')
        if not token:raise VoiceError('ElevenLabs voice pagination was incomplete; refresh the catalog')
    raise VoiceError('Voice catalog is larger than the supported page limit; refine the account library')


def synthesize(text,identity,emotion='neutral',previous_request_ids=None):
    # Conservative documented tags only. Ordinary tags are never sent to VITS/Azure.
    body={'model_id':identity.model,'language_code':'bn','inputs':[{'text':(TAGS.get(emotion,'')+' '+text).strip(),'voice_id':identity.voice_id}]}
    if previous_request_ids:body['previous_request_ids']=previous_request_ids[-3:]
    output=os.getenv('TOON_ELEVENLABS_OUTPUT_FORMAT','mp3_44100_128')
    if output not in ('mp3_44100_128','mp3_44100_192','pcm_44100'):raise VoiceError('Choose a documented ElevenLabs output format supported by your account')
    return fetch('https://api.elevenlabs.io/v1/text-to-dialogue?output_format='+output,headers(),json.dumps(body,ensure_ascii=False).encode())
