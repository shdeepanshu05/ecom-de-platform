import logging
import os
import sys

import google.auth
from google.api_core.exceptions import GoogleAPIError
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import bigquery, storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("verify_adc")

CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


def load_credentials():
    """Find credentials using the ADC search order and resolve the project ID."""
    try:
        credentials, detected_project = google.auth.default(scopes=[CLOUD_PLATFORM_SCOPE])
    except DefaultCredentialsError:
        logger.error("No ADC found. Run: gcloud auth application-default login")
        sys.exit(1)

    project_id = os.getenv("GCP_PROJECT_ID") or detected_project
    if not project_id:
        logger.error("No project ID. Run: gcloud config set project YOUR_PROJECT_ID")
        sys.exit(1)

    logger.info("Credential type: %s", type(credentials).__module__)
    logger.info("Project ID: %s", project_id)
    logger.info("Quota project: %s", getattr(credentials, "quota_project_id", None))
    return credentials, project_id


def check_bigquery(credentials, project_id) -> bool:
    """Run a zero-cost query to prove BigQuery access works."""
    try:
        client = bigquery.Client(project=project_id, credentials=credentials)
        rows = list(client.query("SELECT 1 AS ok").result())
        logger.info("BigQuery OK: query returned %s", rows[0]["ok"])
        return True
    except GoogleAPIError as exc:
        logger.error("BigQuery check failed: %s", exc)
        return False


def check_storage(credentials, project_id) -> bool:
    """List up to 5 buckets to prove Cloud Storage access works."""
    try:
        client = storage.Client(project=project_id, credentials=credentials)
        buckets = [b.name for b in client.list_buckets(max_results=5)]
        logger.info("Cloud Storage OK: %d bucket(s) visible %s", len(buckets), buckets)
        return True
    except GoogleAPIError as exc:
        logger.error("Cloud Storage check failed: %s", exc)
        return False


def main() -> int:
    credentials, project_id = load_credentials()
    results = {
        "bigquery": check_bigquery(credentials, project_id),
        "storage": check_storage(credentials, project_id),
    }
    if all(results.values()):
        logger.info("All checks passed. ADC is configured correctly.")
        return 0
    logger.error("Some checks failed: %s", results)
    return 1


if __name__ == "__main__":
    sys.exit(main())
