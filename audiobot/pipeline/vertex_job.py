from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from . import train_noise as train_mod  # only for module path reference


@dataclass
class VertexConfig:
    project: str
    region: str
    staging_bucket: str
    display_name: str = "audiobot-denoiser-train"
    machine_type: str = "n1-standard-8"
    accelerator_type: Optional[str] = None  # e.g., "NVIDIA_TESLA_T4"
    accelerator_count: int = 1
    container_uri: str = "us-docker.pkg.dev/vertex-ai/training/pytorch-xla.2-2.py310:latest"


def submit_vertex_job(cfg: VertexConfig, script_args: List[str]) -> str:
    """Submit a Vertex AI CustomTrainingJob running the local train script.

    Uses the SDK's code staging for `CustomTrainingJob` with our script path, so
    no manual packaging is required.
    """
    from google.cloud import aiplatform  # type: ignore

    aiplatform.init(project=cfg.project, location=cfg.region, staging_bucket=cfg.staging_bucket)

    script_path = train_mod.__file__  # local path to audiobot/pipeline/train_noise.py
    job = aiplatform.CustomTrainingJob(
        display_name=cfg.display_name,
        script_path=script_path,
        container_uri=cfg.container_uri,
        requirements=[
            "torch>=2.1.0",
            "pytorch-lightning>=2.2.0",
            "torchaudio>=2.1.0",
            "soundfile",
            "librosa",
            "google-cloud-storage",
        ],
    )

    worker_pool_specs = None
    if cfg.accelerator_type:
        worker_pool_specs = [
            {
                "machine_spec": {
                    "machine_type": cfg.machine_type,
                    "accelerator_type": cfg.accelerator_type,
                    "accelerator_count": cfg.accelerator_count,
                },
                "replica_count": 1,
                "container_spec": {
                    "image_uri": cfg.container_uri,
                },
            }
        ]

    model = job.run(
        args=script_args,
        replica_count=1,
        machine_type=cfg.machine_type,
        accelerator_type=cfg.accelerator_type,
        accelerator_count=cfg.accelerator_count if cfg.accelerator_type else None,
        service_account=None,
        environment_variables={"AUDIOBOT_WORK": "/root/audiobot_work"},
        worker_pool_specs=worker_pool_specs,  # type: ignore[arg-type]
        sync=True,
    )
    return str(job.resource_name)

