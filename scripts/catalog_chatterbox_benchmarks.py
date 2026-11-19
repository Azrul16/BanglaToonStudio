"""Catalog downloaded official outputs; never imports their voices into production."""
import hashlib
import json
import re
import wave
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'evaluation/chatterbox-bangla-official'
REV='025a56f71bef7fddc9ee878c9e9557d2ca559499'


def main():
    text=(FOLDER/'README.md').read_text(encoding='utf-8');rows=[]
    for line in text.splitlines():
        if 'audios/output/' not in line or not line.startswith('|'):continue
        identifier=re.search(r'audios/output/(\d+)\.wav',line)[1]
        reference=re.search(r'audios/refs/([^"\s]+)',line)[1]
        path=FOLDER/'audios/output'/(identifier+'.wav')
        with wave.open(str(path),'rb') as wav:
            import audioop
            frames=wav.readframes(wav.getnframes())
            rows.append({'id':identifier,'text':line.rsplit('|',2)[1].strip(),'path':str(path.relative_to(FOLDER)).replace('\\','/'),
                'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'sample_rate':wav.getframerate(),'channels':wav.getnchannels(),
                'duration_seconds':wav.getnframes()/wav.getframerate(),'peak_pcm':audioop.max(frames,wav.getsampwidth()),
                'output_url':f'https://huggingface.co/BosonLab/chatterbox-bangla/resolve/{REV}/audios/output/{identifier}.wav',
                'original_reference_url':f'https://huggingface.co/BosonLab/chatterbox-bangla/resolve/{REV}/audios/refs/{reference}',
                'reference_provenance':'Not established; no permission to clone commercially inferred','production_approved':False})
    assert len(rows)==7 and len({r['id'] for r in rows})==7
    manifest={'model':'BosonLab/chatterbox-bangla','revision':REV,'purpose':'Local pronunciation and audio-quality evaluation only','samples':rows}
    (FOLDER/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Catalogued seven actual WAVs with captions, source URLs, durations and SHA256 hashes')


if __name__=='__main__':main()
