"""Bounded, resumable official-URL downloads when the HF CLI transfer stalls."""
import hashlib
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
REPO='BosonLab/chatterbox-bangla';REV='025a56f71bef7fddc9ee878c9e9557d2ca559499'
ROOT=Path(__file__).resolve().parents[1];FOLDER=ROOT/'models/chatterbox-bangla';FOLDER.mkdir(exist_ok=True)


def download(row):
    name=row['rfilename'];target=FOLDER/name;size=row['size'];sha=row['lfs']['sha256']
    def checksum(path):
        with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
    if target.exists() and checksum(target)==sha:return
    part=target.with_suffix(target.suffix+'.download');offset=part.stat().st_size if part.exists() else 0
    with part.open('ab') as output:
        while offset<size:
            end=min(size-1,offset+16*1024*1024-1)
            for attempt in range(3):
                try:
                    request=urllib.request.Request(f'https://huggingface.co/{REPO}/resolve/{REV}/{name}?download=true&offset={offset}',headers={'Range':f'bytes={offset}-{end}'})
                    with urllib.request.urlopen(request,timeout=30) as response:
                        if response.status!=206 or not response.headers.get('Content-Range','').startswith(f'bytes {offset}-'):raise RuntimeError('Server did not honor the exact resume range')
                        block=response.read(end-offset+1)
                        if len(block)!=end-offset+1:raise RuntimeError('Incomplete download range')
                    break
                except Exception:
                    if attempt==2:raise
                    time.sleep(1)
            output.write(block);output.flush();offset+=len(block)
            print(name,round(offset/size*100,1),'%',flush=True)
    if checksum(part)!=sha:raise RuntimeError('Checkpoint checksum mismatch: '+name)
    part.replace(target)


if __name__=='__main__':
    with urllib.request.urlopen(f'https://huggingface.co/api/models/{REPO}/revision/{REV}?blobs=true',timeout=30) as response:metadata=json.load(response)
    rows=[r for r in metadata['siblings'] if r['rfilename'] in ('t3_cfg.safetensors','s3gen.safetensors')]
    (FOLDER/'download-manifest.json').write_text(json.dumps({'repository':REPO,'revision':REV,'files':rows},indent=2),encoding='utf-8')
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(download,rows))
    print('Verified both official checkpoint SHA-256 hashes',flush=True)
