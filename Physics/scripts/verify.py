#!/usr/bin/env python3
"""Run real adapters and archive machine-readable runtime evidence."""
import importlib.metadata
import json
import platform
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from physim.host import Host

def main():
    report = {'platform': platform.platform(), 'machine': platform.machine(),
              'python': platform.python_version(), 'modules': {}}
    h = Host()
    for name in ['jsbsim', 'coolprop', 'cantera', 'chrono', 'su2', 'sofa', 'precice', 'openvsp', 'fers', 'meep']:
        try:
            states = h.run(name, {'steps': 10} if name in ['jsbsim', 'sofa'] else {})
            report['modules'][name] = {'independently_run': True, 'integrated': True,
                                      'sample_count': len(states), 'last_sample': states[-1]}
            if name in ['jsbsim', 'coolprop', 'cantera']:
                report['modules'][name]['distribution_version'] = importlib.metadata.version(name)
        except Exception as exc:
            report['modules'][name] = {'independently_run': False, 'integrated': False, 'error': str(exc)}
    try:
        result = h.pipeline(json.loads((ROOT / 'examples/atmosphere_pipeline.json').read_text())['jobs'])
        (ROOT / 'artifacts/atmosphere.json').write_text(json.dumps(result, indent=2) + '\n')
        report['coupling'] = {'source': 'jsbsim', 'destination': 'coolprop', 'samples': len(result['air_properties']),
                              'verified': True, 'type': 'one-way sequential data exchange; no feedback'}
    except Exception as exc:
        report['coupling'] = {'verified': False, 'error': str(exc)}
    report['pip_check_passed'] = subprocess.run([sys.executable,'-m','pip','check']).returncode == 0
    (ROOT / 'artifacts/runtime.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    if not report['pip_check_passed'] or not report['coupling']['verified'] or any(not x['integrated'] for x in report['modules'].values()):
        sys.exit(1)

if __name__ == '__main__': main()
