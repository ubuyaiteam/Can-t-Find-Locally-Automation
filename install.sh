#!/usr/bin/env bash
set -e
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
echo "Installed. Start with: bash run.sh"
