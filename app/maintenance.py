"""Explicit disposal of terminal-job render intermediates; no cache deletion."""
import json
import re
from contextlib import nullcontext
from fastapi import APIRouter

def maintenance_router(get_storage,get_lock=nullcontext):
    router=APIRouter()
    def candidates():
        root=get_storage().resolve()
        for job in root.iterdir():
            if not re.fullmatch('[a-f0-9]{32}',job.name) or not job.is_dir() or job.is_symlink():continue
            try:
                state=json.loads((job/'job.json').read_text(encoding='utf-8'))
                if state.get('job_id')!=job.name or state.get('status') not in ('completed','failed','cancelled'):continue
                for file in (job/'render').glob('render_*.avi'):
                    resolved=file.resolve()
                    if re.fullmatch(r'render_\d+\.avi',file.name) and not file.is_symlink() and resolved.is_relative_to(root) and resolved.is_relative_to(job.resolve()) and resolved.is_file():yield resolved
            except (OSError,ValueError):continue
    @router.get('/api/storage/disposable')
    def overview():
        with get_lock():
            files=list(candidates())
            return {'files':len(files),'bytes':sum(p.stat().st_size for p in files if p.exists())}
    @router.post('/api/storage/disposable')
    def cleanup():
        count=0;size=0
        with get_lock():
            for path in list(candidates()):
                if path not in set(candidates()):continue
                try:
                    amount=path.stat().st_size;path.unlink();count+=1;size+=amount
                except OSError:continue
        return {'removed_files':count,'removed_bytes':size}
    return router
