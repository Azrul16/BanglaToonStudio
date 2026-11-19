"""Compatibility entry point for the strict typed screenplay interpreter."""
from app.assets import speaker_info,registry
from app.screenplay import RuleBasedScriptInterpreter,spoken_rows


def parse_story(story,speaker_resolver=None,split_narration=False,character_aliases=None,location_aliases=None,corrections=None):
    resolve=speaker_resolver or speaker_info
    if character_aliases is None:
        reg=registry()
        character_aliases=[a for cid,row in reg['speakers'].items() if not row['off_screen'] for a in [cid,*row['aliases']]]
    if location_aliases is None:location_aliases=[a for terms in registry()['locations'].values() for a in terms]
    screenplay=RuleBasedScriptInterpreter(resolve,character_aliases,location_aliases).interpret(story,corrections)
    segments=spoken_rows(screenplay.events,resolve)
    return {'events':[e.model_dump() for e in screenplay.events],'segments':segments,'speakers':list(dict.fromkeys(s['speaker'] for s in segments)),
            'count':len(segments),'event_count':len(screenplay.events),'schema_version':2}
