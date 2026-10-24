#!/usr/bin/env python3
"""Export auditable local evidence and upstream license originals for version control."""
import hashlib
import json
import platform
import re
import shutil
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def read(name):
    p=ROOT/'artifacts'/name
    return json.loads(p.read_text()) if p.exists() else {}

def main():
    evidence=ROOT/'evidence'; evidence.mkdir(exist_ok=True)
    locks=json.loads((ROOT/'dependencies.lock.json').read_text())['modules']
    acquired,built,runtime=read('fetch.json'),read('build.json'),read('runtime.json')
    status={'verification_date':datetime.now(ZoneInfo('America/New_York')).isoformat(), 'platform':platform.platform(),
            'machine':platform.machine(), 'modules':{}}
    licenses=[]
    for name,lock in locks.items():
        src=ROOT/lock['source_dir']
        files=set()
        for pattern in ['LICENSE*','COPYING*','COPYRIGHT*','License*']:
            files.update(p for p in src.glob(pattern) if p.is_file())
        for path in sorted(files):
            target=ROOT/'licenses'/name/path.name
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(path,target)
            licenses.append({'module':name,'commit':lock['commit'],'upstream_file':path.name,
                             'local_file':str(target.relative_to(ROOT)),
                             'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
        run=runtime.get('modules',{}).get(name,{})
        build=built.get(name,{})
        status['modules'][name]={
            'version':lock['ref'],'commit':lock['commit'],'mode':lock['mode'],
            'acquired':acquired.get(name,{}).get('acquired',False),
            'configured':build.get('configured',False),
            'built_from_source':build.get('built_from_source',False),
            'installed_binary_wheel':name in ['jsbsim','coolprop','cantera'] and run.get('integrated',False),
            'independently_run':run.get('independently_run',False),
            'integrated':run.get('integrated',False),
            'coupling_verified':name in ['jsbsim','coolprop'] and runtime.get('coupling',{}).get('verified',False),
            'error':run.get('error') or build.get('error'),
            'local_diff':subprocess.check_output(['git','diff','--stat'],cwd=src,text=True).strip() if (src/'.git').exists() else None}
        state=status['modules'][name]
        state['state']=('coupling_verified' if state['coupling_verified'] else
                        'integrated' if state['integrated'] else
                        'built' if state['built_from_source'] else
                        'blocked' if state['error'] else 'acquired')
        log=ROOT/'artifacts/logs'/f'{name}-build.log'
        if log.exists():
            content=log.read_text(errors='replace').replace(str(ROOT),'<PHYSICS>')
            (evidence/f'{name}-build-tail.txt').write_text('\n'.join(content.splitlines()[-65:])+'\n')
            lines=content.splitlines()
            selected=set()
            for i,line in enumerate(lines):
                if re.search(r'CMake Error|fatal error:|BLOCKED:|mandatory|Could not set',line):
                    selected.update(range(max(0,i-3), min(len(lines),i+12)))
            if selected:
                (evidence/f'{name}-diagnostics.txt').write_text('\n'.join(lines[i] for i in sorted(selected))+'\n')
    for name in ['runtime.json','build.json','fetch.json']:
        p=ROOT/'artifacts'/name
        if p.exists(): (evidence/name).write_text(p.read_text().replace(str(ROOT),'<PHYSICS>'))
    for name in ['tests.txt','chrono.json','su2.json','lock-install.txt']:
        p=ROOT/'artifacts'/name
        if p.exists(): shutil.copyfile(p,evidence/name)
    (evidence/'status.json').write_text(json.dumps(status,indent=2)+'\n')
    (ROOT/'licenses/index.json').write_text(json.dumps(licenses,indent=2)+'\n')
    print(json.dumps(status,indent=2))

if __name__=='__main__':main()
