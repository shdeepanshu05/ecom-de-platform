"""Shared runtime settings: which project, which scale, which paths.

Values come from environment variables, falling back to your gcloud/ADC project,
so no script needs a hardcoded project ID.
    GCP_PROJECT_ID   project to use (default: the project ADC / gcloud is set to)
    DATA_SCALE       sample | medium | large (default: sample)
"""
import os

import google.auth


def resolve_project_id() -> str:
    """GCP_PROJECT_ID env var first, then the project from ADC / gcloud config."""
    project_id = os.getenv("GCP_PROJECT_ID")
    if not project_id:
        _, project_id = google.auth.default()
    if not project_id:
        raise RuntimeError(
            "No project ID. Set GCP_PROJECT_ID or run: gcloud config set project YOUR_PROJECT_ID"
        )
    return project_id


def data_scale() -> str:
    """Which dataset size to work with."""
    return os.getenv("DATA_SCALE", "sample")


def raw_uri(project_id: str, scale: str) -> str:
    """GCS location of the batch backfill files. Bucket naming matches Terraform."""
    return f"gs://{project_id}-raw/ecommerce/batch_backfill/{scale}"