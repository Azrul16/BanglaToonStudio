"""Install the official Rhubarb release locally without changing system PATH."""
import io
import json
import os
import platform
import stat
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

VERSION = "1.14.0"


def install():
    system = {"Windows": "Windows", "Linux": "Linux", "Darwin": "macOS"}.get(platform.system())
    if not system:
        raise RuntimeError("Unsupported platform; install Rhubarb manually and set RHUBARB_BINARY.")
    request = urllib.request.Request(
        f"https://api.github.com/repos/DanielSWolf/rhubarb-lip-sync/releases/tags/v{VERSION}",
        headers={"User-Agent": "BanglaToonStudio"})
    with urllib.request.urlopen(request, timeout=30) as response:
        release = json.load(response)
    asset = next(a for a in release["assets"] if system in a["name"] and a["name"].endswith(".zip"))
    print(f"Downloading official {asset['name']}…", flush=True)
    with urllib.request.urlopen(asset["browser_download_url"], timeout=120) as response:
        archive = response.read()
    target = Path(__file__).resolve().parents[1] / "tools/rhubarb"
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        names = [PurePosixPath(i.filename).parts for i in zipped.infolist() if i.filename]
        roots = {parts[0] for parts in names}
        strip = len(roots) == 1 and any(len(parts) > 1 for parts in names)
        for info in zipped.infolist():
            parts = PurePosixPath(info.filename).parts
            if strip:
                parts = parts[1:]
            if not parts:
                continue
            destination = target.joinpath(*parts).resolve()
            if not destination.is_relative_to(target.resolve()) or stat.S_ISLNK(info.external_attr >> 16):
                raise RuntimeError("Unsafe archive entry")
            if info.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(zipped.read(info))
    binary = target / ("rhubarb.exe" if os.name == "nt" else "rhubarb")
    if not binary.is_file():
        raise RuntimeError("Release layout changed; install manually and set RHUBARB_BINARY.")
    if os.name != "nt":
        binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
    print(f"Installed {binary}. Restart the studio to refresh tool status.")


if __name__ == "__main__":
    install()
