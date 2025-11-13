from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Dict

def upload_if_configured(local_path: str) -> Optional[Dict[str, str]]:
    """
    Upload `local_path` to GCS if env is configured.
    Requires:
      - GCS_BUCKET
      - Optional: GCS_PREFIX (default: audiobot/outputs)
      - GOOGLE_APPLICATION_CREDENTIALS set to a JSON key (or VM default creds)
    Returns dict with gs_uri and object_name, or None if not configured.
    """
    bucket_name = os.getenv("GCS_BUCKET")
    if not bucket_name:
        return None
    try:
        from google.cloud import storage  # type: ignore
    except Exception:
        return None

    try:
        client = storage.Client()  # uses default or GOOGLE_APPLICATION_CREDENTIALS
        bucket = client.bucket(bucket_name)
        prefix = os.getenv("GCS_PREFIX", "audiobot/outputs").strip("/")
        fname = Path(local_path).name
        obj_name = f"{prefix}/{fname}" if prefix else fname
        blob = bucket.blob(obj_name)
        blob.upload_from_filename(local_path)
        return {"gs_uri": f"gs://{bucket_name}/{obj_name}", "object_name": obj_name}
    except Exception:
        return None
