"""Offline verification of the pinned Bengali weights and tokenizer."""
import hashlib
import json
from pathlib import Path

def verify_checkpoint(folder,manifest=None):
    expected=json.loads(Path(manifest or Path(__file__).with_name('chatterbox-checkpoint.json')).read_text(encoding='utf-8'))
    for name,sha in expected['sha256'].items():
        path=Path(folder)/name
        if not path.resolve().is_relative_to(Path(folder).resolve()):raise ValueError('Invalid checkpoint manifest path')
        with path.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
        if actual!=sha:raise ValueError('Bengali checkpoint/tokenizer checksum mismatch: '+name)
    return expected
