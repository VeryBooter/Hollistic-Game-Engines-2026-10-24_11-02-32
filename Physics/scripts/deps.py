#!/usr/bin/env python3
"""Fetch pinned upstream Git repositories without changing the parent Git index."""
import argparse
import concurrent.futures
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / 'dependencies.lock.json').read_text())['modules']

def fetch(name):
    entry = LOCK[name]
    dest = ROOT / entry['source_dir']
    log = ROOT / 'artifacts' / 'logs' / (name + '-fetch.log')
    log.parent.mkdir(parents=True, exist_ok=True)
    dest.mkdir(parents=True, exist_ok=True)
    try:
        with log.open('w') as out:
            def run(*args):
                subprocess.run(args, cwd=dest, stdout=out, stderr=subprocess.STDOUT,
                               check=True, timeout=600)
            if not (dest / '.git').exists():
                run('git', 'init')
                run('git', 'remote', 'add', 'origin', entry['repository'])
            remote = subprocess.check_output(['git', 'remote', 'get-url', 'origin'], cwd=dest, text=True).strip()
            if remote != entry['repository']:
                raise RuntimeError('Unexpected origin: ' + remote)
            if subprocess.check_output(['git', 'status', '--porcelain'], cwd=dest, text=True).strip():
                actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=dest, text=True).strip()
                if actual == entry['commit']:
                    return name, {'acquired': True, 'commit': actual, 'locally_modified': True,
                                  'note': 'Already at locked commit; local changes preserved without checkout',
                                  'log': str(log.relative_to(ROOT))}
                raise RuntimeError('Refusing to overwrite modified upstream checkout at a different commit')
            run('git', 'fetch', '--depth=1', 'origin', entry['commit'])
            run('git', 'checkout', '--detach', entry['commit'])
            actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=dest, text=True).strip()
            if actual != entry['commit']:
                raise RuntimeError('Commit mismatch')
        return name, {'acquired': True, 'commit': actual, 'log': str(log.relative_to(ROOT))}
    except (subprocess.SubprocessError, RuntimeError) as exc:
        return name, {'acquired': False, 'error': str(exc), 'log': str(log.relative_to(ROOT))}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['fetch', 'verify', 'submodules'])
    p.add_argument('modules', nargs='+', choices=[*LOCK, 'all'])
    args = p.parse_args()
    names = list(LOCK) if 'all' in args.modules else args.modules
    if args.action == 'submodules':
        for name in names:
            if name == 'radarsim':
                raise SystemExit('RadarSimCpp requires separate source access; not fetching private SSH dependency')
            subprocess.run(['git', 'submodule', 'update', '--init', '--recursive', '--depth=1'],
                           cwd=ROOT / LOCK[name]['source_dir'], check=True)
        return
    if args.action == 'verify':
        for name in names:
            dest = ROOT / LOCK[name]['source_dir']
            actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=dest, text=True).strip()
            if actual != LOCK[name]['commit']:
                raise SystemExit('Commit mismatch: ' + name)
            print(name, actual)
        return
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = dict(pool.map(fetch, names))
    report = ROOT / 'artifacts' / 'fetch.json'
    previous = json.loads(report.read_text()) if report.exists() else {}
    previous.update(results)
    report.write_text(json.dumps(previous, indent=2) + '\n')
    print(json.dumps(results, indent=2))
    if any(not x['acquired'] for x in results.values()):
        sys.exit(1)

if __name__ == '__main__':
    main()
