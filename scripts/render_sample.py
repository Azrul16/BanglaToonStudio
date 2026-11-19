"""Render the built-in story through a running studio's actual HTTP API."""
import argparse
import json
import time
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", choices=["vits"], default="vits")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    def request(path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(args.url+path, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)

    health = request('/api/health')
    created = request('/api/generate', {"story": health['sample_story']})
    print('Job:', created['job_id'], flush=True)
    previous = None
    while True:
        job = request('/api/jobs/'+created['job_id'])
        state = (job['status'], job['stage'], job['progress'])
        if state != previous:
            print(*state, flush=True)
            previous = state
        if job['status'] == 'completed':
            print(json.dumps(job, ensure_ascii=True, indent=2))
            return
        if job['status'] in ('failed', 'cancelled'):
            raise RuntimeError(job.get('error', job['status']))
        time.sleep(1)


if __name__ == '__main__':
    main()
