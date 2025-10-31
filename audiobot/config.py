import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass


@dataclass
class Settings:
    bearer_token: str = os.getenv("BEARER_TOKEN", "change-me")
    ipfs_api: str = os.getenv("IPFS_API", "http://127.0.0.1:5001")
    ipfs_gateway: str = os.getenv("IPFS_GATEWAY", "http://127.0.0.1:8080")
    gcp_credentials: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    gcs_bucket: str = os.getenv("GCS_BUCKET", "")
    gcs_prefix: str = os.getenv("GCS_PREFIX", "deliverables/")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    verse_interval_sec: int = int(os.getenv("AUDIOBOT_VERSE_INTERVAL_SEC", "15"))


SETTINGS = Settings()
