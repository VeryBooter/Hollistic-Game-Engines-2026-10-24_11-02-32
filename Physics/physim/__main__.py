import argparse
import json
from pathlib import Path
from .host import Host

def main():
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['list', 'run', 'pipeline'])
    p.add_argument('target', nargs='?')
    p.add_argument('--config', type=Path)
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    host = Host()
    if args.action == 'list': result = host.registry
    elif args.action == 'run':
        result = host.run(args.target, json.loads(args.config.read_text()) if args.config else {})
    else:
        result = host.pipeline(json.loads(Path(args.target).read_text())['jobs'])
    text = json.dumps(result, indent=2, allow_nan=False) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    else: print(text, end='')

if __name__ == '__main__': main()
