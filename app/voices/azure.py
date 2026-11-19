"""Azure regional REST synthesis with actual regional voice availability."""
import json
import os
import re
from xml.sax.saxutils import escape
from app.voices.base import fetch,VoiceError

ALLOWED={'bn-BD-PradeepNeural','bn-BD-NabanitaNeural'}


def endpoint():
    region=os.getenv('AZURE_SPEECH_REGION','')
    key=os.getenv('AZURE_SPEECH_KEY','')
    if not key or not re.fullmatch(r'[a-z0-9]+',region):raise VoiceError('Set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION in the server environment')
    return f'https://{region}.tts.speech.microsoft.com/cognitiveservices',{'Ocp-Apim-Subscription-Key':key}


def voices():
    base,headers=endpoint();raw,_=fetch(base+'/voices/list',headers,timeout=30)
    return [{'provider':'azure','voice_id':r['ShortName'],'name':r.get('DisplayName',r['ShortName']),
             'labels':{'gender':r.get('Gender'),'locale':r.get('Locale')},'description':'Bangladesh Bengali Neural voice'}
            for r in json.loads(raw) if r.get('ShortName') in ALLOWED]


def synthesize(text,identity,emotion='neutral'):
    if identity.voice_id not in ALLOWED:raise VoiceError('Only verified bn-BD voices are supported by this Azure adapter')
    base,headers=endpoint();headers.update({'Content-Type':'application/ssml+xml','X-Microsoft-OutputFormat':'riff-24khz-16bit-mono-pcm','User-Agent':'BanglaToonStudio'})
    # These bn-BD voices do not advertise expressive styles. Do not invent SSML styles.
    ssml=f'<speak version="1.0" xml:lang="bn-BD"><voice name="{identity.voice_id}">{escape(text)}</voice></speak>'
    return fetch(base+'/v1',headers,ssml.encode('utf-8'))
