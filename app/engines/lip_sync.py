"""Phonetic Rhubarb cues, with an offline audio-envelope fallback."""
import json
import math
import os
import shutil
import subprocess
import sys
import wave
from array import array
from pathlib import Path


def rhubarb_binary():
    configured = os.getenv("RHUBARB_BINARY")
    if configured:
        return shutil.which(configured)
    root = Path(__file__).resolve().parents[2]
    for folder in ('tools/rhubarb', '.tools/rhubarb'):
        local = root / folder / ("rhubarb.exe" if os.name == "nt" else "rhubarb")
        if local.is_file(): return str(local)
    return shutil.which("rhubarb")


def validate_cues(result, duration):
    if not isinstance(result, dict) or not isinstance(result.get('mouthCues'), list):
        raise ValueError('Rhubarb returned no cue list')
    previous = 0.
    for cue in result['mouthCues']:
        start, end = cue.get('start'), cue.get('end')
        if (cue.get('value') not in tuple('ABCDEFGHX') or not isinstance(start,(int,float)) or not isinstance(end,(int,float))
                or not math.isfinite(start) or not math.isfinite(end) or start < previous or end <= start or end > duration+.08):
            raise ValueError('Invalid or overlapping Rhubarb mouth-cue timestamps')
        cue['end'] = min(end, duration)
        previous = end
    return result


def generate_mouth_cues(audio_path: Path, output_path: Path, mode: str = "auto") -> dict:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    binary = rhubarb_binary()
    reason = None
    with wave.open(str(audio_path), 'rb') as wav:
        duration = wav.getnframes()/wav.getframerate()
    if binary and mode != "envelope":
        try:
            subprocess.run([binary, "-r", "phonetic", "-f", "json", "-o", str(output_path), str(audio_path)],
                           check=True, capture_output=True, timeout=180,
                           creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            result = validate_cues(json.loads(output_path.read_text(encoding="utf-8")), duration)
            result.update(method='rhubarb', approximate=True)
            output_path.write_text(json.dumps(result, indent=2), encoding='utf-8')
            return result
        except (OSError, subprocess.SubprocessError, ValueError, TypeError) as exc:
            reason = f'Rhubarb failed; approximate audio-envelope fallback: {exc}'
    elif mode != 'envelope':
        reason = 'Rhubarb executable not found; approximate audio-envelope fallback.'
    with wave.open(str(audio_path), "rb") as wav:
        if wav.getsampwidth() != 2:
            raise ValueError("Lip sync requires 16-bit PCM WAV audio")
        rate, channels = wav.getframerate(), wav.getnchannels()
        samples = array("h", wav.readframes(wav.getnframes()))
    if sys.byteorder != "little": samples.byteswap()
    step = max(1, round(rate * .08)) * channels
    levels = [math.sqrt(sum(v*v for v in samples[i:i+step]) / max(1, len(samples[i:i+step])))
              for i in range(0, len(samples), step)]
    peak = max(levels, default=0)
    cues = []
    for i, level in enumerate(levels):
        ratio = level / peak if peak else 0
        value = "X" if ratio < .08 else "B" if ratio < .3 else "C" if ratio < .65 else "D"
        start, end = i * step / channels / rate, min((i+1)*step, len(samples)) / channels / rate
        if cues and cues[-1]["value"] == value: cues[-1]["end"] = end
        else: cues.append({"start": start, "end": end, "value": value})
    result = {"method": "envelope", "mouthCues": cues, "approximate": True, "fallback_reason": reason}
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def mouth_at(cues: list[dict], time: float) -> str:
    for cue in cues:
        if cue["start"] <= time < cue["end"]:
            return cue["value"]
    return "X"
