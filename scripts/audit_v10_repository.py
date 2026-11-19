"""Read-only inventory and source checkpoint before v10 cleanup."""
import ast
import json
import zipfile
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def sha(path):
    import hashlib
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    target=ROOT/'workspace/v10-baseline-source.zip'
    files=[p for folder in ('app','scripts','tests','godot/scripts','godot/scenes','docs') for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    files += [p for p in ROOT.iterdir() if p.is_file() and p.suffix in ('.py','.md','.txt','.bat','.cmd','.ini')]
    files += [ROOT/'godot/project.godot',ROOT/'assets/registry.json',ROOT/'assets/voice_references/four_voices.json',ROOT/'workspace/preferences.json']
    if not target.exists():
        with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
            for path in dict.fromkeys(files):
                if path.is_file():archive.write(path,path.relative_to(ROOT))
    from app.main import app,LIBRARY
    from app.voices.four_voices import configuration
    library=LIBRARY.refresh()
    imports={}
    for path in (ROOT/'app').rglob('*.py'):
        tree=ast.parse(path.read_text(encoding='utf-8'));imports[str(path.relative_to(ROOT))]=[
            n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
    snapshot={'archive':str(target),'entry_points':['Bangla Toon Studio.exe','scripts/desktop_launcher.py','scripts/desktop_server.py','run.py','start.bat'],
        'active_api_paths':list(app.openapi()['paths']),'imports':imports,
        'characters':{k:r['status'] for k,r in library.characters.items()},'backgrounds':{k:r['status'] for k,r in library.backgrounds.items()},
        'voice_mode':configuration().get('mode'),'selected_demo_ids':configuration().get('official_evaluation_selections'),
        'assets':{str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'assets').rglob('*') if p.is_file()},
        'existing_mp4':{str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'output').glob('*.mp4')}}
    path=ROOT/'workspace/v10-baseline-inventory.json'
    if not path.exists():path.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Source checkpoint:',target);print('API paths:',len(snapshot['active_api_paths']));print('Preserved assets:',len(snapshot['assets']));print('Existing videos:',len(snapshot['existing_mp4']))


if __name__=='__main__':main()
