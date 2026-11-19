"""Decode real exports and audit subtitle/continuity traces, not UI placeholders."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.audit_v4_media import audit
from app.scene_cache import atomic_json
from app.hardware import ffmpeg_binary,run


def main():
    source=json.loads((ROOT/'workspace/v7-chatterbox-evaluation/acceptance.json').read_text(encoding='utf-8'))
    results=[]
    for entry in source['videos']:
        result=audit(entry);directory=ROOT/'workspace'/entry['job_id']
        timeline=json.loads((directory/'timeline.json').read_text(encoding='utf-8'))
        direction=json.loads((directory/'direction.json').read_text(encoding='utf-8'))
        assert len(timeline['subtitles'])==5
        for scene in timeline['scenes']:
            if scene['kind']!='speech':continue
            cue=scene['subtitle']
            assert cue['start']==scene['start'] and abs(cue['end']-scene['start']-scene['audio_duration'])<1e-9
            assert len(cue['lines'])<=2 and not cue['background_box'] and not cue['speaker_prefix']
            assert cue['text']==scene['text'] and '(' not in cue['text']
        subtitle_frames=0;clear_frames=0
        for path in (directory/'render').glob('*-poses.jsonl'):
            for line in path.read_text(encoding='utf-8').splitlines():
                row=json.loads(line);clock=row['frame']/30
                scene=next(s for s in direction if s['start']<=clock<s['end'])
                cue=scene.get('subtitle') if scene['kind']=='speech' else scene.get('screen_text_asset')
                visible=bool(cue and cue['start']<=clock<cue['end'])
                assert row['subtitle_visible']==visible
                assert row['subtitle_text']==(cue['text'] if visible else '')
                subtitle_frames+=visible;clear_frames+=not visible
        assert subtitle_frames and clear_frames
        speech=[s for s in direction if s['kind']=='speech']
        assert speech[0]['actors']['nabil']['emotion']=='fear'
        assert speech[3]['actors']['nabil']['emotion_state']['emotion']=='embarrassed'
        assert speech[4]['actors']['rayan']['emotion_state']['emotion']=='relieved'
        def root(actor,t):
            p=max(0.,min(1.,(t-actor['start'])/max(.01,actor['end']-actor['start'])));p=p*p*(3-2*p)
            return actor['from_x']+(actor['to_x']-actor['from_x'])*p
        for before,after in zip(direction,direction[1:]):
            for cid in before['actors'].keys() & after['actors'].keys():
                assert abs(root(before['actors'][cid],before['end'])-root(after['actors'][cid],after['start']))<.001
        for label,clock in [('subtitle',(speech[0]['start']+speech[0]['subtitle']['end'])/2),('clear',.5),('emotion',(speech[3]['start']+speech[3]['end'])/2)]:
            output=ROOT/'workspace'/(entry['job_id']+'-'+label+'.png')
            command=run([ffmpeg_binary(),'-y','-v','error','-ss',str(clock),'-i',entry['video'],'-frames:v','1',str(output)],60)
            assert command.returncode==0,command.stderr
        result.update(subtitle_cues=5,subtitle_trace_rows=subtitle_frames,clear_trace_rows=clear_frames,
            max_subtitle_lines=max(len(s['lines']) for s in timeline['subtitles']),subtitle_timing='full actual WAV duration',
            continuity_checked=True,emotional_changes_checked=['afraid','embarrassed','relieved'])
        results.append(result)
    atomic_json(ROOT/'workspace/v7-media-audit.json',{'videos':results,'human_pronunciation_review':'pending','reference_conditioning':'blocked: authorized recordings not supplied'})
    print(json.dumps(results),flush=True)


if __name__=='__main__':main()
