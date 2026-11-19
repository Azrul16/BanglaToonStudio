"""Native portrait contract shared by every production renderer and validator."""
import logging
VIDEO_WIDTH=1080
VIDEO_HEIGHT=1920
VIDEO_FPS=30
VIDEO_ASPECT_RATIO='9:16'
VIDEO_ORIENTATION='portrait'
STAGE_WIDTH=720
STAGE_HEIGHT=1280
PROFILES={'production':(VIDEO_WIDTH,VIDEO_HEIGHT),'low_memory':(720,1280)}

def validate_canvas(width,height,fps=VIDEO_FPS):
    if (width,height) not in PROFILES.values() or width*16!=height*9 or fps!=VIDEO_FPS:
        message=f'Portrait-only export rejected {width}x{height} at {fps} FPS; use 1080x1920 or explicit 720x1280 at 30 FPS.'
        logging.getLogger('bangla_toon.video').error(message);raise ValueError(message)
    return width,height

def output_size(options=None):
    options=options or {}
    if options.get('video_format','auto') not in ('auto','vertical','portrait'):raise ValueError('Landscape and square export are prohibited; every new video is portrait 9:16.')
    profile=options.get('video_profile','production')
    if profile not in PROFILES:raise ValueError('Unknown portrait export profile')
    if options.get('fps',VIDEO_FPS)!=VIDEO_FPS:raise ValueError('New cartoons must use 30 FPS')
    return PROFILES[profile]
