"""Write generated data to local CSV files and optionally upload them to GCS."""
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def write_csv(df: pd.DataFrame, path: Path) -> Path:
    """Write a DataFrame as a CSV with a header row, creating folders as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    logger.info("Wrote %s rows to %s", f"{len(df):,}", path)
    return path


def upload_to_gcs(local_root: Path, gcs_uri: str, files: list[Path]) -> None:
    """Upload files to gs://bucket/prefix, keeping their path relative to local_root.

    Uses Application Default Credentials: your user locally, the service
    account when running on Cloud Run.
    """
    from google.cloud import storage  # imported here so local-only runs don't need it

    if not gcs_uri.startswith("gs://"):
        raise ValueError(f"Expected a gs:// URI, got {gcs_uri}")
    bucket_name, _, prefix = gcs_uri[len("gs://"):].partition("/")
    bucket = storage.Client().bucket(bucket_name)

    for file in files:
        relative = file.relative_to(local_root).as_posix()
        blob_name = f"{prefix.rstrip('/')}/{relative}" if prefix else relative
        bucket.blob(blob_name).upload_from_filename(str(file), timeout=600)
        logger.info("Uploaded gs://%s/%s", bucket_name, blob_name)
