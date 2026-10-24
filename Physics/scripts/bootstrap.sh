#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
PYTHON="${PHYSICS_PYTHON:-python3}"
"$PYTHON" -c 'import sys,platform; assert sys.version_info[:2] == (3,10), "Use CPython 3.10 for this wheel lock"; assert platform.system() == "Darwin" and platform.machine() == "arm64", "This lock targets macOS arm64"'
"$PYTHON" -m venv .venv
.venv/bin/python -m pip install --require-hashes --only-binary=:all: -r requirements-macos-arm64.lock.txt
.venv/bin/python -m pip check
