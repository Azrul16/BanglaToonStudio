"""Shared output dimensions and duration targets; speech is never stretched."""
from app.video_config import output_size


def duration_target(options=None):
    return (120,180) if (options or {}).get('duration_mode')=='mini' else (30,40)
