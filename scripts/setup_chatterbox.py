"""Reproduce the isolated Windows runtime using the app's matching Torch binaries."""
import json
import os
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
COMMIT='2a6aba38365782fce8258a6f51708ac19c8093ce'


def run(*args):subprocess.run([str(a) for a in args],cwd=ROOT,check=True)


def main():
    if sys.version_info[:2]!=(3,11):raise SystemExit('Use the application Python 3.11 interpreter')
    import torch,torchaudio
    if torch.__version__!=torchaudio.__version__:raise SystemExit('Torch and torchaudio versions must match before setup')
    env=ROOT/'.chatterbox-venv'
    if not (env/'Scripts/python.exe').exists():run(sys.executable,'-m','venv',env)
    site=env/'Lib/site-packages';original=ROOT/'.venv/Lib/site-packages'
    import _winapi
    for name in ['torch','torchgen','functorch','torchaudio','torio',*[p.name for pattern in ('torch-*.dist-info','torchaudio-*.dist-info') for p in original.glob(pattern)]]:
        if not (site/name).exists():_winapi.CreateJunction(str(original/name),str(site/name))
    run(env/'Scripts/python.exe','-m','pip','install','-r',ROOT/'requirements-chatterbox.txt')
    toolkit=ROOT/'tools/chatterbox-finetuning'
    if not toolkit.exists():
        run('git','clone','--no-checkout','https://github.com/gokhaneraslan/chatterbox-finetuning',toolkit)
        run('git','-C',toolkit,'checkout',COMMIT)
    current=subprocess.check_output(['git','-C',str(toolkit),'rev-parse','HEAD'],text=True).strip()
    if current!=COMMIT:raise SystemExit('Toolkit revision differs. Keep existing changes; use the documented pinned revision in a separate checkout.')
    path=toolkit/'src/chatterbox_/tts.py';text=path.read_text(encoding='utf-8')
    if 'T3Config(text_tokens_dict_size=t3_state[' not in text:
        text=text.replace('        t3 = T3()\n','')
        marker='        t3.load_state_dict(t3_state)'
        if marker not in text:raise SystemExit('Unexpected loader layout; patch was not applied')
        text=text.replace(marker,'        from .models.t3.modules.t3_config import T3Config\n        t3 = T3(hp=T3Config(text_tokens_dict_size=t3_state["text_emb.weight"].shape[0]))\n'+marker)
        path.write_text(text,encoding='utf-8')
    if 'del t3_state' not in text:
        text=text.replace('        t3.to(device).eval()','        t3.to(device).eval()\n        del t3_state')
        path.write_text(text,encoding='utf-8')
    run(env/'Scripts/python.exe','-m','pip','check')
    print('Runtime prepared. Download pinned model files using hf, then run scripts/benchmark_chatterbox.py.')


if __name__=='__main__':main()
