"""Stable saved identities first, then explicitly reviewed category defaults."""
import os
from app.voices import voice_manager
from app.voices.base import VoiceIdentity
from app.voices.studio import registry,category_for


def resolve_voices(library,segments,preference='saved'):
    library.refresh()
    saved=voice_manager.settings(library.storage);presets=registry(library.storage).voice_categories
    selected_provider=os.getenv('DEFAULT_TTS_PROVIDER','chatterbox_bangla') if preference=='saved' else preference
    identities={};issues=[]
    for segment in segments:
        cid=segment['speaker']
        if cid in identities:continue
        # Asset review owns unresolved names. Never assign a real voice before
        # the user has mapped the speaker to a validated character or role.
        if cid not in library.characters and cid not in ('narrator','unknown_voice'):
            identities[cid]=None;continue
        if preference=='vits':identities[cid]=VoiceIdentity().model_dump();continue
        if selected_provider=='chatterbox_bangla':
            from app.voices.four_voices import reference,category_for as voice_category,configuration,SETTINGS
            from app.voices.chatterbox_bangla import MODEL_REVISION,CACHE_VERSION
            category=voice_category(cid,library.characters.get(cid))
            try:
                profile,_=reference(category)
                from app.voices.variation import dsp_capabilities,VERSION as DSP_VERSION
                preset={**configuration()['character_presets'][cid],'processor':dsp_capabilities(),'cache_schema':DSP_VERSION}
                identities[cid]=VoiceIdentity(provider='chatterbox_bangla',model='BosonLab/chatterbox-bangla',voice_id=cid,
                    reference_audio_hash=profile['sha256'],model_revision=MODEL_REVISION,generation_settings=SETTINGS,synthesis_version=CACHE_VERSION,
                    category=category,variation=preset,usage_mode=configuration().get('mode','production'),official_sample_id=profile.get('official_sample_id')).model_dump()
            except ValueError:
                identities[cid]=None
                if not any(i.get('category')==category for i in issues):issues.append({'type':'voice','source_text':category.replace('_',' ').title(),'reason':'category_reference_required','category':category,'provider':'chatterbox_bangla','message':category.replace('_',' ').title()+' voice is not configured. Open Default Cartoon Voices in Settings.'})
            continue
        if cid in saved:identities[cid]=saved[cid];continue
        category=category_for(library.characters[cid]) if cid in library.characters else 'male'
        accepted=[p for p in presets[category] if p.bengali_reviewed and (not category.startswith('child_') or p.accept_alternative)
                  and (preference=='saved' or p.voice.provider==preference)]
        if accepted:
            identities[cid]=voice_manager.remember_approved_default(library.storage,cid,accepted[-1].voice) if cid in library.characters or cid in ('narrator','unknown_voice') else accepted[-1].voice.model_dump()
        elif preference in ('saved','vits'):identities[cid]=VoiceIdentity().model_dump()
        else:
            identities[cid]=None
            issues.append({'type':'voice','source_text':segment['speaker_name'],'speaker_id':cid,'reason':'selection_required',
                           'category':category,'provider':preference,'message':'একবার এই চরিত্রের জন্য একটি উপলব্ধ কণ্ঠ নির্বাচন করুন।'})
    return identities,issues
