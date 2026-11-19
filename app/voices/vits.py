"""One genuine local voice; never advertise synthetic pitch variants as people."""
from app.engines.bangla_tts import synthesize

def voices():return [{'provider':'vits','voice_id':'default_bn','name':'Bangladeshi VITS (single voice)','labels':{'language':'bn'},'description':'Offline; no supported emotional style controls'}]
