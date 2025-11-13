#!/usr/bin/env bash
set -euo pipefail

# Try common conda locations on Lightning Studio
if [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
  source "$HOME/miniconda3/etc/profile.d/conda.sh"
elif [ -f "/teamspace/studios/this_studio/miniconda3/etc/profile.d/conda.sh" ]; then
  source "/teamspace/studios/this_studio/miniconda3/etc/profile.d/conda.sh"
fi

if ! command -v conda >/dev/null 2>&1; then
  echo "conda not found; please ensure Miniconda is installed on the VM" >&2
  exit 1
fi

conda env list | grep -q "^audio\s" || conda create -y -n audio python=3.12
conda run -n audio python -m pip install --upgrade pip
conda run -n audio python -m pip install -r requirements.txt
conda run -n audio python -m pip install -e . || true

mkdir -p logs
nohup conda run -n audio uvicorn web.app:app --host 0.0.0.0 --port 8000 > logs/web_8000.log 2>&1 &
nohup conda run -n audio uvicorn web.litserve_app:app --host 0.0.0.0 --port 8080 > logs/lit_8080.log 2>&1 &

echo "Services started. Check logs/"
