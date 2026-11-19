"""Pinned official Windows Godot download, verified against release SHA-512."""
import hashlib
import io
import sys
import urllib.request
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VERSION='4.7.2-stable'

if __name__=='__main__':
    folder=ROOT/'tools/godot';folder.mkdir(parents=True,exist_ok=True)
    name=f'Godot_v{VERSION}_win64.exe.zip';base=f'https://github.com/godotengine/godot-builds/releases/download/{VERSION}/'
    sums=urllib.request.urlopen(base+'SHA512-SUMS.txt',timeout=45).read().decode()
    payload=urllib.request.urlopen(base+name,timeout=180).read()
    expected=next(line.split()[0] for line in sums.splitlines() if line.endswith(name))
    if hashlib.sha512(payload).hexdigest()!=expected:raise RuntimeError('Godot checksum mismatch')
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for entry in archive.namelist():
            if entry.endswith('.exe') and '/' not in entry and '\\' not in entry:(folder/entry).write_bytes(archive.read(entry))
    (folder/'SHA512-SUMS.txt').write_text(sums,encoding='utf-8')
    print('Installed official checksum-verified Godot',VERSION)
