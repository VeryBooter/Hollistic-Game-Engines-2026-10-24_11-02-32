import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from .contract import ROOT, validate

class Host:
    """One active isolated job per host; deterministic, dependency-ordered scheduling."""
    def __init__(self, registry=None):
        self.registry = registry or json.loads((ROOT / 'modules.json').read_text())
        self.process = None

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
            try: self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait()

    def run(self, name, config=None, inputs=None, timeout=60):
        if self.process is not None and self.process.poll() is None:
            raise RuntimeError('Host already running a job')
        entry = self.registry[name]
        if not entry['enabled']: raise RuntimeError(f'{name} is disabled: {entry.get("reason", "not configured")}')
        for state in inputs or []: validate(state)
        with tempfile.TemporaryDirectory(prefix='physim-') as temp:
            folder = Path(temp)
            request, response = folder / 'request.json', folder / 'response.json'
            request.write_text(json.dumps(dict(module=name, config=config or {}, inputs=inputs or []), allow_nan=False))
            with (folder / 'worker.log').open('w+') as log:
                self.process = subprocess.Popen([sys.executable, '-m', 'physim.worker', str(request), str(response)],
                    cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    self.process.wait(timeout=timeout)
                finally:
                    self.stop()
                log.seek(0)
                logs = log.read()
                if not response.exists(): raise RuntimeError(f'{name}: no response\n{logs[-4000:]}')
                answer = json.loads(response.read_text())
                if self.process.returncode or not answer['ok']:
                    raise RuntimeError(f'{name}: {answer.get("error")}\n{logs[-4000:]}')
                if isinstance(answer['result'], list):
                    for state in answer['result']: validate(state)
                return answer['result']

    def pipeline(self, jobs):
        results = {}
        for job in jobs:
            if job['id'] in results: raise ValueError('Duplicate job id')
            source = job.get('input_from')
            if source is not None and source not in results:
                raise ValueError('Input must refer to an earlier job')
            if source is not None:
                states = results[source]
                if not isinstance(states, list): raise ValueError('Source has no parsed exchange packets')
                times = [s['time_s'] for s in states]
                if any(a >= b for a,b in zip(times,times[1:])):
                    raise ValueError('Source times must be strictly increasing')
            results[job['id']] = self.run(job['module'], job.get('config'),
                                          results[source] if source else None, job.get('timeout_s', 60))
        return results
