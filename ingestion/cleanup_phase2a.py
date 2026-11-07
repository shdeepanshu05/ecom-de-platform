"""Delete Phase 2A data: raw files in GCS and Bronze tables in BigQuery.

Destructive, so it shows which project it will touch and asks you to type that
project ID before deleting anything.

Run:  python -m ingestion.cleanup_phase2a
Uses GCP_PROJECT_ID / DATA_SCALE if set, otherwise your gcloud/ADC project and "sample".
"""
import logging
import sys

from google.api_core.exceptions import NotFound
from google.cloud import bigquery, storage

from ingestion.settings import data_scale, raw_uri, resolve_project_id

BRONZE_TABLES = ["customers", "products", "orders", "order_items"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger("cleanup_phase2a")


def delete_gcs_prefix(project_id: str, gcs_uri: str) -> int:
    """Delete every object under gs://bucket/prefix/. Returns the number deleted."""
    bucket_name, _, prefix = gcs_uri[len("gs://"):].partition("/")
    client = storage.Client(project=project_id)
    blobs = list(client.list_blobs(bucket_name, prefix=prefix.rstrip("/") + "/"))
    for blob in blobs:
        blob.delete()
    logger.info("Deleted %d objects under %s", len(blobs), gcs_uri)
    return len(blobs)


def delete_bronze_tables(project_id: str) -> None:
    """Drop the Bronze tables (the dataset itself stays; Terraform owns it)."""
    client = bigquery.Client(project=project_id)
    for table in BRONZE_TABLES:
        table_id = f"{project_id}.bronze.{table}"
        client.delete_table(table_id, not_found_ok=True)
        logger.info("Dropped %s (if it existed)", table_id)


def main() -> int:
    project_id = resolve_project_id()
    target_uri = raw_uri(project_id, data_scale())

    print(f"This deletes all files under {target_uri}")
    print(f"and the Bronze tables {BRONZE_TABLES} in project {project_id}.")
    if input("Type the project ID to confirm: ").strip() != project_id:
        print("Not confirmed. Nothing deleted.")
        return 1
    try:
        delete_gcs_prefix(project_id, target_uri)
        delete_bronze_tables(project_id)
    except NotFound as exc:
        logger.error("Resource not found: %s", exc)
        return 1
    logger.info("Cleanup finished.")
    return 0


if __name__ == "__main__":
    sys.exit(main())