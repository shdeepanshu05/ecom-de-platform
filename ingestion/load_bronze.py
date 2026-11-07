"""Load raw CSV exports from GCS into BigQuery Bronze tables.

Bronze principle: store the data *as received*. Every column is loaded as STRING,
so a malformed date or a stray value can never make the load fail. Parsing,
typing and cleaning happen in Silver (Phase 3), where bad rows can be inspected.

Usage:
    python -m ingestion.load_bronze --project ecom-de-dev-3552 \
        --source gs://ecom-de-dev-3552-raw/ecommerce/batch_backfill/sample
    python -m ingestion.load_bronze ... --dry-run     # print what would run
"""
import argparse
import logging
import sys

from google.api_core.exceptions import GoogleAPIError
from google.cloud import bigquery

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger("load_bronze")

# Column order must match the CSV header order. New columns are only ever added at
# the END (coupon_code), so older files with fewer columns still line up.
ENTITIES = {
    "customers": ["customer_id", "first_name", "last_name", "email", "phone", "city",
                  "state", "country", "preferred_currency", "signup_ts"],
    "products": ["product_id", "sku", "product_name", "category", "brand", "list_price", "currency"],
    "orders": ["order_id", "customer_id", "order_ts", "status", "currency", "payment_method",
               "shipping_country", "item_count", "order_total", "coupon_code"],
    "order_items": ["order_item_id", "order_id", "product_id", "quantity", "unit_price", "line_total"],
}


def build_job_config(columns: list[str]) -> bigquery.LoadJobConfig:
    """Load settings shared by every Bronze table."""
    return bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,                       # first line is the header
        schema=[bigquery.SchemaField(c, "STRING") for c in columns],
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,  # full reload = idempotent
        allow_jagged_rows=True,                    # rows missing trailing columns -> NULL
        max_bad_records=0,                         # fail loudly on structurally broken files
        labels={"layer": "bronze", "pipeline": "batch_backfill"},
    )


def load_entity(client: bigquery.Client, project: str, dataset: str, source: str,
                entity: str, dry_run: bool) -> None:
    """Load every file under <source>/<entity>/ into <dataset>.<entity>."""
    uri = f"{source.rstrip('/')}/{entity}/*"     # '*' matches all objects under that prefix
    table_id = f"{project}.{dataset}.{entity}"
    config = build_job_config(ENTITIES[entity])
    if dry_run:
        logger.info("[dry-run] would load %s -> %s", uri, table_id)
        return

    job = client.load_table_from_uri(uri, table_id, job_config=config)
    logger.info("Started job %s: %s -> %s", job.job_id, uri, table_id)
    job.result()  # wait; raises if the job failed
    table = client.get_table(table_id)
    logger.info("Loaded %s: %s rows, %.1f MB", table_id, f"{table.num_rows:,}", table.num_bytes / 1e6)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Load raw CSVs from GCS into BigQuery Bronze.")
    parser.add_argument("--project", required=True)
    parser.add_argument("--dataset", default="bronze")
    parser.add_argument("--source", required=True, help="gs://bucket/prefix that contains entity folders")
    parser.add_argument("--entities", nargs="+", default=list(ENTITIES), choices=list(ENTITIES))
    parser.add_argument("--location", default="us-central1")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    # A dry run makes no API calls, so it doesn't need credentials.
    client = None if args.dry_run else bigquery.Client(project=args.project, location=args.location)
    failed = []
    for entity in args.entities:
        try:
            load_entity(client, args.project, args.dataset, args.source, entity, args.dry_run)
        except GoogleAPIError as exc:
            # Keep going so one bad entity doesn't block the others; report at the end.
            logger.error("Loading %s failed: %s", entity, exc)
            failed.append(entity)
    if failed:
        logger.error("Failed entities: %s", failed)
        return 1
    logger.info("All entities loaded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
