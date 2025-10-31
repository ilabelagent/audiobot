Holy Spirit Vocal Engine (AudioBot)

Overview
- Local-first audio processing toolkit with CLI + FastAPI.
- Goals: denoise, de-ess, reduce harshness/sibilance, normalize loudness, stem separation, batch runs.
- Extensible for IPFS/GCS, Windows FL Studio workflows, and Lightning AI deployment.

Quick Start (local, Windows)
- Create Conda env:
  - conda create -y -n audio python=3.12
  - conda activate audio
  - pip install -U pip
  - pip install -r requirements.txt
- Optional: pip install -e .  (enables `audiobot` command)
- Run CLI help: audiobot -h
- Start Web UI/API: audiobot serve-web --host 0.0.0.0 --port 8000
  - Open http://localhost:8000/ for the UI

Endpoints
- GET /health — liveness
- POST /process — multipart file upload, returns cleaned file
  - Form fields: target_lufs (float), no_deess (bool), download (bool), to_gcs (bool), to_ipfs (bool)
  - If to_gcs/to_ipfs are true and env is configured, uploads to GCS and/or pins to IPFS; response includes meta.gcs/meta.ipfs
- POST /batch — JSON manifest { files:["path"...], out_dir?, target_lufs?, no_deess?, to_gcs?, to_ipfs? }
- POST /preset — upload a preset JSON for later use

CLI
- audiobot clean input.wav -o outputs/clean.wav
- audiobot batch path/to/folder -o outputs/
- audiobot stems input.wav -o outputs/stems/
- audiobot serve-web -H 0.0.0.0 -p 8000
- audiobot serve-lit -H 0.0.0.0 -p 8080

Env (.env or environment vars)
- BEARER_TOKEN=change-me
- IPFS_API=http://127.0.0.1:5001
- IPFS_GATEWAY=http://127.0.0.1:8080
- GOOGLE_APPLICATION_CREDENTIALS=Z:\\Projects\\audiobot\\peaceful-access-473817-v1-b6c23a77fab4.json
- GCS_BUCKET=hsve-processed
- GCS_PREFIX=deliverables/

Auth
- If `BEARER_TOKEN` is not "change-me" or empty, all endpoints require `Authorization: Bearer <token>`

Lightning AI (deploy sketch)
1) SSH to Studio VM and create the same Conda env.
2) pip install -r requirements.txt
3) Start services:
   - uvicorn audiobot.web.app:app --host 0.0.0.0 --port 8000
   - python -m audiobot serve-lit -H 0.0.0.0 -p 8080
4) Optionally create systemd user units (see scripts/systemd/).

Windows deploy helper
- scripts\deploy\deploy_lightning.ps1
  - Packages repo, scp to Lightning, unzips to /teamspace/studios/this_studio/jesus-cartel-production
  - Runs scripts/deploy/setup_conda_vm.sh to create env and start services

Notes
- Audio DSP uses numpy/librosa/pyloudnorm if present; otherwise falls back to passthrough.
- Demucs stem separation is optional and requires torch+demucs installed.
- See requirements.txt and environment.yml for suggested stacks.

UI customization
- Rotating verses: add your own lines (one per line) to `data/verses.txt`. The UI loads these in addition to packaged defaults and rotates without repeats per cycle.
- Verse rotation interval: set `AUDIOBOT_VERSE_INTERVAL_SEC` (default: 15). Example PowerShell: `$env:AUDIOBOT_VERSE_INTERVAL_SEC = "20"`
- External verses source (optional): set `AUDIOBOT_VERSES_URL` to a text file URL (one verse per line) to include additional verses dynamically.
- Fast mode: on the index page, enable "Fast mode (quicker, lighter)" for a quicker ffmpeg chain with gentler settings.
- Progress hints: during processing, the overlay cycles human-friendly step hints. No setup needed.

Verses file tips
- A sample file is provided at `data/verses.sample.txt`. Copy it to `data/verses.txt` and edit.
- `data/verses.txt` is git-ignored by default to keep your personal list private.
