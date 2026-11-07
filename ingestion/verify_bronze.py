"""Verify the raw files in GCS and the Bronze tables in BigQuery, using Python only.

Every query is dry-run first to show how many bytes it would scan, and runs with
maximum_bytes_billed so an accidentally expensive query is refused, not billed.
"""
import logging

from google.cloud import bigquery, storage

logger = logging.getLogger("verify_bronze")

MAX_BYTES_BILLED = 1_000_000_000  # 1 GB safety cap per query


def list_raw_files(gcs_uri: str) -> None:
    """Print a count and total size of files per top-level folder under gcs_uri."""
    bucket_name, _, prefix = gcs_uri[len("gs://"):].partition("/")
    prefix = prefix.rstrip("/") + "/"
    summary: dict[str, list[int]] = {}
    for blob in storage.Client().list_blobs(bucket_name, prefix=prefix):
        folder = blob.name[len(prefix):].split("/", 1)[0]
        count_and_bytes = summary.setdefault(folder, [0, 0])
        count_and_bytes[0] += 1
        count_and_bytes[1] += blob.size or 0
    if not summary:
        logger.warning("No files found under %s", gcs_uri)
    for folder, (count, size) in sorted(summary.items()):
        logger.info("GCS %-15s %4d files  %8.2f MB", folder, count, size / 1e6)


def run_query(client: bigquery.Client, title: str, sql: str) -> list[dict]:
    """Dry-run the query to show its cost, then run it with a bytes cap and print rows."""
    dry = client.query(sql, job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False))
    logger.info("[%s] will scan %.2f MB", title, dry.total_bytes_processed / 1e6)

    config = bigquery.QueryJobConfig(maximum_bytes_billed=MAX_BYTES_BILLED)
    rows = [dict(row) for row in client.query(sql, job_config=config).result()]
    logger.info("[%s] results:", title)
    for row in rows:
        logger.info("    %s", row)
    return rows


def verify_bronze(project: str, dataset: str = "bronze", location: str = "us-central1") -> None:
    """Row counts, injected data-quality defects, and schema evolution in Bronze."""
    client = bigquery.Client(project=project, location=location)
    table = f"`{project}.{dataset}"

    run_query(client, "row counts", f"""
        SELECT 'customers' AS tbl, COUNT(*) AS row_count FROM {table}.customers` UNION ALL
        SELECT 'products', COUNT(*) FROM {table}.products` UNION ALL
        SELECT 'orders', COUNT(*) FROM {table}.orders` UNION ALL
        SELECT 'order_items', COUNT(*) FROM {table}.order_items`
    """)

    run_query(client, "data-quality defects in orders", f"""
        SELECT
          COUNT(*) - COUNT(DISTINCT order_id)                          AS duplicate_rows,
          COUNTIF(customer_id IS NULL)                                 AS null_customer,
          COUNTIF(SAFE_CAST(customer_id AS INT64) NOT IN (
                    SELECT SAFE_CAST(customer_id AS INT64) FROM {table}.customers`)) AS orphan_customer,
          COUNTIF(order_ts LIKE '%/%')                                 AS ddmmyyyy_timestamps,
          COUNTIF(status != UPPER(status))                             AS messy_status,
          COUNTIF(coupon_code IS NOT NULL)                             AS has_coupon
        FROM {table}.orders`
    """)

    run_query(client, "schema evolution (coupons appear from 2025-07)", f"""
        SELECT SUBSTR(order_ts, 1, 7) AS order_month,
               COUNTIF(coupon_code IS NOT NULL) AS orders_with_coupon
        FROM {table}.orders`
        WHERE order_ts LIKE '2025-0%'
        GROUP BY order_month
        ORDER BY order_month
    """)
