#!/usr/bin/env bash
set -euo pipefail
PYTHONPATH=src python3 src/main.py "$@"
