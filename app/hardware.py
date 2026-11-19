"""Measured hardware capabilities; encoding probes are real, not name checks."""
import importlib.util
import json
import os
import shutil
import subprocess
import threading
import time
from functools import lru_cache
from pathlib import Path
import psutil


def ffmpeg_binary():
    return shutil.which(os.getenv('FFMPEG_BINARY','ffmpeg'))


def ffprobe_binary():
    configured=os.getenv('FFPROBE_BINARY')
    if configured:
        return shutil.which(configured)
    binary=ffmpeg_binary()
    sibling=Path(binary).with_name('ffprobe.exe' if os.name=='nt' else 'ffprobe') if binary else None
    return str(sibling) if sibling and sibling.is_file() else shutil.which('ffprobe')


def run(command,timeout=30):
    return subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout,
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)


@lru_cache(maxsize=1)
def encoder_capabilities():
    binary=ffmpeg_binary()
    result={'ffmpeg':binary,'ffprobe':ffprobe_binary(),'encoder':'libx264','nvenc_tested':False,'nvenc_available':False,'libx264_available':False}
    if not binary:
        result['reason']='FFmpeg not found on PATH.'; return result
    for encoder in ('libx264','h264_nvenc'):
        command=[binary,'-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=black:s=720x1280:r=24',
                 '-frames:v','8','-c:v',encoder,'-preset','p4' if encoder=='h264_nvenc' else 'veryfast','-pix_fmt','yuv420p','-f','null','-']
        started=time.perf_counter()
        try:
            probe=run(command)
            passed=probe.returncode==0
            result[encoder+'_probe_seconds']=round(time.perf_counter()-started,4)
            result['nvenc_available' if encoder=='h264_nvenc' else 'libx264_available']=passed
            if not passed: result[encoder+'_error']=probe.stderr[-1200:]
        except (OSError,subprocess.TimeoutExpired) as exc:
            result[encoder+'_error']=str(exc)
        if encoder=='h264_nvenc': result['nvenc_tested']=True
    if result['nvenc_available']: result['encoder']='h264_nvenc'
    return result


@lru_cache(maxsize=1)
def hardware_info():
    result={**encoder_capabilities(),'cpu_count':os.cpu_count(),'ram_gb':round(psutil.virtual_memory().total/1024**3,2),
            'nvidia':None,'cuda_available':False,'tts_installed':importlib.util.find_spec('TTS') is not None,'sprite_renderer':'CPU Pillow'}
    binary=shutil.which('nvidia-smi')
    if binary:
        try:
            probe=run([binary,'--query-gpu=name,memory.total,driver_version','--format=csv,noheader,nounits'],10)
            if probe.returncode==0: result['nvidia']=probe.stdout.strip()
        except (OSError,subprocess.TimeoutExpired): pass
    if importlib.util.find_spec('torch'):
        try:
            import torch
            result.update(torch_version=torch.__version__,cuda_available=torch.cuda.is_available(),torch_cuda_version=torch.version.cuda)
            if result['cuda_available']: result['cuda_device']=torch.cuda.get_device_name(0)
        except Exception as exc:
            result['cuda_error']=str(exc)
    return result


def validate_video(path,expected_duration,check_cancel=lambda:None,size=None,fps=30):
    from app.video_config import validate_canvas,VIDEO_WIDTH,VIDEO_HEIGHT
    size=size or (VIDEO_WIDTH,VIDEO_HEIGHT)
    validate_canvas(*size,fps)
    probe=ffprobe_binary()
    if not probe: raise RuntimeError('ffprobe is required to validate output; install it alongside FFmpeg.')
    check_cancel()
    info=run([probe,'-v','error','-show_streams','-show_format','-of','json',str(path)],60)
    if info.returncode: raise RuntimeError('ffprobe rejected the output: '+info.stderr[-1500:])
    try:
        data=json.loads(info.stdout)
        video=next(s for s in data['streams'] if s['codec_type']=='video')
        audio=next(s for s in data['streams'] if s['codec_type']=='audio')
        n,d=map(int,video['r_frame_rate'].split('/'))
        duration=float(data['format']['duration'])
        validate_canvas(video['width'],video['height'],n/d)
        if video.get('sample_aspect_ratio','1:1')!='1:1':raise ValueError('non-square or unknown pixels violate portrait display aspect')
        rotation=float(video.get('tags',{}).get('rotate',0))
        rotation=next((float(s.get('rotation',0)) for s in video.get('side_data_list',[]) if 'rotation' in s),rotation)
        if rotation%180:raise ValueError('rotation metadata would display the video horizontally')
        if (video['width'],video['height'],video['codec_name'],video['pix_fmt'])!=(*size,'h264','yuv420p') or n/d!=fps or audio['codec_name']!='aac':
            raise ValueError('unexpected output streams')
        if abs(duration-expected_duration)>.15: raise ValueError('audio/video duration differs from timeline')
    except (KeyError,ValueError,StopIteration,ZeroDivisionError) as exc:
        raise RuntimeError('Invalid MP4 streams or synchronization: '+str(exc)) from exc
    check_cancel()
    decoded=run([ffmpeg_binary(),'-v','error','-xerror','-i',str(path),'-f','null','-'],180)
    if decoded.returncode: raise RuntimeError('MP4 integrity validation failed: '+decoded.stderr[-1500:])
    check_cancel()
    return {'duration_seconds':round(duration,4),'width':size[0],'height':size[1],'fps':fps,'video_codec':'h264','audio_codec':'aac','pixel_format':'yuv420p','orientation':'portrait','aspect_ratio':'9:16','validated':True}


class ResourceMonitor:
    """One low-overhead sampler covering this process and encoder subprocesses."""
    def __init__(self):
        self.peak_rss=0
        self.stop_event=threading.Event()
        self.thread=threading.Thread(target=self.sample,daemon=True)

    def sample(self):
        process=psutil.Process()
        while not self.stop_event.is_set():
            try:
                total=process.memory_info().rss
                for child in process.children(recursive=True):
                    try: total+=child.memory_info().rss
                    except psutil.Error: pass
                self.peak_rss=max(self.peak_rss,total)
            except psutil.Error: pass
            self.stop_event.wait(.25)

    def __enter__(self):
        self.thread.start(); return self

    def __exit__(self,*args):
        self.stop_event.set(); self.thread.join(timeout=2)

    @property
    def peak_mb(self):
        return round(self.peak_rss/1024**2,1)
