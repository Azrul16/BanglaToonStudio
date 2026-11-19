"""Conservative scene-level emotion evidence, separate from scene/music mood."""
import re
from app.assets import normalize

# Semantic emotions use only expressions that the current rig actually supports.
EMOTION_RIG={'neutral':'neutral','happy':'happy','excited':'excited','curious':'curious','confused':'confused','surprised':'surprised',
    'afraid':'fear','nervous':'worried','angry':'angry','sad':'sad','embarrassed':'worried','proud':'happy','thinking':'thinking',
    'suspicious':'curious','relieved':'happy','playful':'laugh'}
ALIASES={'fear':'afraid','worried':'nervous','laugh':'playful','cry':'sad','whisper':'neutral'}
EVIDENCE={
 'afraid':('ভয় পেয়ে','ভয় পেয়ে','ভয়ে','ভয়ে','ভয় লাগছে','ভয় লাগছে','ওরে বাবা','ভীত'),
 'nervous':('নার্ভাস','ঘাবড়ে','ঘাবড়ে','দুশ্চিন্তা','স্নায়ুচাপে'),
 'embarrassed':('লজ্জা পেয়ে','লজ্জায়','লজ্জায়','অপ্রস্তুত','বিব্রত'),
 'proud':('গর্ব করে','গর্বিত','গর্বে','গর্বের সঙ্গে'),
 'suspicious':('সন্দেহ করে','সন্দেহের','সন্দেহভরে','সন্দেহজনক'),
 'relieved':('স্বস্তি','হাঁফ ছেড়ে','হাঁফ ছেড়ে','ভয় নেই','ভয় নেই','ভয় পাইনি','ভয় পাইনি'),
 'thinking':('চুপ করে ভাব','ভাবতে লাগ','চিন্তা করে','ভাবনায়','ভাবনায়'),
 'playful':('দুষ্টুমি','মজা করে','হেসে বল','হাসতে হাসতে'),
 'happy':('খুশি','আনন্দে','আনন্দিত'), 'sad':('মন খারাপ','দুঃখ','কাঁদ','কষ্ট পেয়'),
 'angry':('রাগ করে','রাগে','রেগে','ক্ষুব্ধ'), 'surprised':('চমকে','অবাক','আশ্চর্য'),
 'curious':('কৌতূহল','কৌতূহলী'), 'confused':('বিভ্রান্ত','বুঝতে পারছে না','বুঝলাম না'),
 'excited':('উত্তেজিত','উচ্ছ্বসিত')}


class EmotionAnalyzer:
    def infer(self,text):
        value=normalize(text)
        if value in EMOTION_RIG:return value,1.,[value]
        # Negative fear evidence must be resolved before positive substrings.
        order=['relieved']+[k for k in EVIDENCE if k!='relieved']
        for name in order:
            matches=[p for p in EVIDENCE[name] if normalize(p) in value]
            matches=[p for p in matches if not re.search(re.escape(normalize(p))+r'\s+(?:না|নই|নয়|নয়)(?:\s|[।.!?]|$)',value)]
            if matches:return name,min(.94,.78+.06*(len(matches)-1)),matches
        return None

    def apply(self,events,resolve):
        states={};scene=None
        for event in events:
            if event.scene_id!=scene:scene=event.scene_id;states={}
            if event.type not in ('action','dialogue','narration','emotion'):continue
            labels=[event.speaker_label] if event.generate_voice else event.character_labels
            ids=[]
            for label in labels:
                if not label:continue
                try:cid=resolve(label)['character_id']
                except ValueError:continue
                if cid not in ('unresolved','narrator','unknown_voice') and cid not in ids:ids.append(cid)
            explicit=event.metadata.get('delivery_tag')
            # Stage text supplies emotion evidence; spoken text can supply emotion,
            # never physical actions. Negated emotion is handled by infer().
            evidence=self.infer(explicit or event.metadata.get('attribution_context') or event.text)
            if event.generate_voice and not explicit and not event.metadata.get('attribution_context'):
                # Asking about another person's fear/sadness is not evidence that
                # the speaker has that emotion. Prefer their established state.
                self_report=re.search(r'আমি|আমার|আমাকে|লাগছে|ওরে বাবা|স্বস্তি|ভ[য়য়]+ নেই',normalize(event.text))
                if not self_report:evidence=None
            if explicit and normalize(explicit) in ('neutral','normal','স্বাভাবিক'):
                evidence=('neutral',1.,[explicit])
            existing=event.emotion
            if evidence:semantic,confidence,triggers=evidence
            elif existing!='neutral' and not event.metadata.get('emotion_inherited'):
                semantic=ALIASES.get(existing,existing);confidence=.9;triggers=[explicit or 'recognized delivery/action']
            else:semantic=None;confidence=0.;triggers=[]
            rows=[]
            for cid in ids:
                if semantic:
                    states[cid]={'character_id':cid,'emotion':semantic,'rig_emotion':EMOTION_RIG.get(semantic,existing),
                        'confidence':confidence,'trigger_event':event.event_id,'evidence':triggers}
                state=states.setdefault(cid,{'character_id':cid,'emotion':'neutral','rig_emotion':'neutral','confidence':1.,'trigger_event':event.event_id,'evidence':['initial state']})
                rows.append(dict(state))
            if rows:
                event.metadata['emotion_states']=rows
                if len(rows)==1:event.emotion=rows[0]['rig_emotion']
        return events
