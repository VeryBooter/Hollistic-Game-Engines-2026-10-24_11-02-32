#!/usr/bin/env python3
"""Generate hashes from downloaded wheels; run only when deliberately updating pins."""
import hashlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
lines = ['# CPython 3.10, macOS arm64 >= 14.0. Includes all runtime transitive dependencies.']
for path in sorted((ROOT / 'artifacts/wheels').glob('*.whl')):
    name, version = path.name.split('-')[:2]
    lines.append(f'{name}=={version} --hash=sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}')
if len(lines) != 13: raise SystemExit('Expected exactly 12 pinned wheels')
(ROOT / 'requirements-macos-arm64.lock.txt').write_text('\n'.join(lines) + '\n')
