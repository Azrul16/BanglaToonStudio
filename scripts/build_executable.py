"""Rebuild the small Windows launcher using an isolated PyInstaller environment."""
import subprocess
from pathlib import Path
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]


if __name__=='__main__':
    icon=Image.new('RGBA',(256,256))
    draw=ImageDraw.Draw(icon)
    draw.rounded_rectangle((8,8,248,248),radius=54,fill='#142131')
    draw.rounded_rectangle((43,70,213,204),radius=18,fill='#e0b879')
    draw.polygon([(109,108),(109,174),(163,141)],fill='#142131')
    draw.rounded_rectangle((39,46,211,80),radius=8,fill='#e0b879')
    for x in (70,115,160): draw.polygon([(x,46),(x+20,46),(x+4,80),(x-16,80)],fill='#142131')
    path=ROOT/'assets/launcher.ico'
    icon.save(path,sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
    python=ROOT/'.build-venv/Scripts/python.exe'
    if not python.is_file(): raise SystemExit('Create .build-venv with Python 3.11 and install requirements-build.txt first.')
    subprocess.run([str(python),'-m','PyInstaller','--noconfirm','--clean','--onefile','--console',
                    '--name','Bangla Toon Studio','--icon',str(path),'--distpath',str(ROOT),
                    '--workpath',str(ROOT/'.launcher-build/work'),'--specpath',str(ROOT/'.launcher-build'),
                    str(ROOT/'scripts/desktop_launcher.py')],cwd=ROOT,check=True)
