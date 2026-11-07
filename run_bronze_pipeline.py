"""Phase 2A pipeline in one Python script: generate -> upload to GCS -> load Bronze -> verify.

Run it with the VS Code Run button (open this file, click the triangle at the top right)
or with:  python run_bronze_pipeline.py

Configuration comes from environment variables, so the same code works for any project:
    GCP_PROJECT_ID   project to use (default: the project your gcloud/ADC is set to)
    DATA_SCALE       sample | medium | large (default: sample)
"""
import logging
import os
import sys

import google.auth

from generator.main import parse_args, run as generate_and_upload
from ingestion.load_bronze import main as load_bronze
from ingestion.verify_bronze import list_raw_files, verify_bronze

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger("run_bronze_pipeline")

# Which steps to run (set False to skip a step you've already done).
RUN_GENERATE_AND_UPLOAD = True
RUN_LOAD_BRONZE = True
RUN_VERIFY = True


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


def main() -> int:
    project_id = resolve_project_id()
    scale = os.getenv("DATA_SCALE", "sample")
    local_dir = f"data/{scale}"
    raw_uri = f"gs://{project_id}-raw/ecommerce/batch_backfill/{scale}"
    logger.info("Project: %s | scale: %s | raw: %s", project_id, scale, raw_uri)

    if RUN_GENERATE_AND_UPLOAD:
        logger.info("STEP 1: generate %s data and upload to %s", scale, raw_uri)
        generate_and_upload(parse_args(["--scale", scale, "--output-dir", local_dir, "--gcs-uri", raw_uri]))

    if RUN_LOAD_BRONZE:
        logger.info("STEP 2: load GCS files into BigQuery bronze")
        if load_bronze(["--project", project_id, "--source", raw_uri]) != 0:
            logger.error("Bronze load failed; stopping.")
            return 1

    if RUN_VERIFY:
        logger.info("STEP 3: verify raw files and bronze tables")
        list_raw_files(raw_uri)
        verify_bronze(project_id)

    logger.info("Phase 2A pipeline finished.")
    return 0


if __name__ == "__main__":
    sys.exit(main())