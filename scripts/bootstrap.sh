#!/usr/bin/env bash
set -euo pipefail

if [[ ! -d .venv ]]; then
  python -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .[dev]

echo "Bootstrap complete. Run: source .venv/bin/activate && make dev"
