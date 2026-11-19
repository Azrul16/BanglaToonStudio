"""Measure one device per process to avoid holding CPU and CUDA model copies."""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.engines.bangla_tts import VITSTTSEngine
from app.hardware import ResourceMonitor


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--device',choices=['cpu','cuda'],required=True)
    args=parser.parse_args()
    directory=ROOT/'workspace/benchmarks'; directory.mkdir(exist_ok=True)
    engine=VITSTTSEngine(device=args.device)
    with ResourceMonitor() as monitor:
        started=time.perf_counter(); engine.load()
        load=time.perf_counter()-started
        runs=[]
        for index in range(3):
            started=time.perf_counter()
            duration=engine.synthesize('শান্ত থাকুন, সবকিছু ঠিক হয়ে যাবে।',directory/f'{args.device}_{index}.wav')
            elapsed=time.perf_counter()-started
            runs.append({'seconds':elapsed,'audio_seconds':duration,'real_time_factor':elapsed/duration})
        report={'requested_device':args.device,'actual':engine.report(),'load_wall_seconds':load,'runs':runs,
                'warm_mean_seconds':sum(r['seconds'] for r in runs[1:])/2,'peak_process_tree_rss_mb':monitor.peak_mb}
    (directory/f'{args.device}.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
