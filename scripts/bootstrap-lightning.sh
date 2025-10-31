#!/usr/bin/env bash
set -euo pipefail

# Optional: export these before running or edit here
: "${AUDIOBOT_DIR:=$HOME/audiobot}"
: "${CONDA_DIR:=$HOME/miniconda3}"
: "${ENV_NAME:=audio}"
: "${PORT_WEB:=8000}"
: "${PORT_LIT:=8080}"

echo "[+] Updating packages and installing ffmpeg..."
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update -y && sudo apt-get install -y ffmpeg git curl unzip
fi

if [ ! -d "$CONDA_DIR" ]; then
  echo "[+] Installing Miniconda..."
  curl -fsSL https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -o /tmp/m.sh
  bash /tmp/m.sh -b -p "$CONDA_DIR"
fi
source "$CONDA_DIR/etc/profile.d/conda.sh"
conda activate || true

if ! conda env list | grep -q "^$ENV_NAME\s"; then
  echo "[+] Creating conda env $ENV_NAME..."
  conda create -y -n "$ENV_NAME" python=3.12
fi
conda activate "$ENV_NAME"

echo "[+] Installing Python deps..."
pip install --upgrade pip
pip install fastapi uvicorn[standard] demucs litserve openai anthropic google-generativeai google-cloud-storage

if [ -d "$AUDIOBOT_DIR" ]; then
  echo "[+] Using existing repo at $AUDIOBOT_DIR"
else
  echo "[!] Repo directory $AUDIOBOT_DIR not found. Clone or rsync your code here."
  exit 1
fi

cd "$AUDIOBOT_DIR"
pip install -e .

echo "[+] Launching web (port $PORT_WEB) and litserve (port $PORT_LIT) via nohup..."
nohup uvicorn web.app:app --host 0.0.0.0 --port "$PORT_WEB" >/tmp/audiobot-web.log 2>&1 &
nohup python -m audiobot serve-lit -H 0.0.0.0 -p "$PORT_LIT" >/tmp/audiobot-lit.log 2>&1 &

echo "[+] Done. Logs: /tmp/audiobot-web.log, /tmp/audiobot-lit.log"

