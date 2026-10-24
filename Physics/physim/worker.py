import json
import sys
import traceback
from pathlib import Path
from .adapters import ADAPTERS, external_run
from .contract import validate

def main():
    request, response = map(Path, sys.argv[1:3])
    try:
        job = json.loads(request.read_text())
        name = job['module']
        for state in job.get('inputs', []): validate(state)
        result = (ADAPTERS[name](job.get('config', {}), job.get('inputs', []))
                  if name in ADAPTERS else external_run(name, job.get('config', {}), job.get('inputs', [])))
        if isinstance(result, list):
            for state in result: validate(state)
        response.write_text(json.dumps({'ok': True, 'result': result}, allow_nan=False) + '\n')
    except Exception as exc:
        response.write_text(json.dumps({'ok': False, 'error': str(exc)}) + '\n')
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__': main()
