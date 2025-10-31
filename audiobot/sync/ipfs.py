from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Dict

import requests  # type: ignore


def pin_file(local_path: str) -> Optional[Dict[str, str]]:
    """
    Add a file to IPFS via HTTP API and pin it.
    Env:
      - IPFS_API (e.g., http://127.0.0.1:5001)
      - IPFS_GATEWAY (optional, for building a view URL)
    Returns dict with cid, gateway_url if successful, else None.
    """
    api = os.getenv("IPFS_API")
    if not api:
        return None
    api = api.rstrip("/")
    url = f"{api}/api/v0/add?pin=true"
    with open(local_path, "rb") as f:
        files = {"file": (Path(local_path).name, f)}
        try:
            r = requests.post(url, files=files, timeout=60)
            r.raise_for_status()
        except Exception:
            return None
    data = r.json()
    cid = data.get("Hash") or data.get("Cid") or ""
    out: Dict[str, str] = {"cid": cid}
    gw = os.getenv("IPFS_GATEWAY", "https://ipfs.io").rstrip("/")
    if cid:
        out["gateway_url"] = f"{gw}/ipfs/{cid}"
    return out

