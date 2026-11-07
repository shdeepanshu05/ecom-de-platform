"""Command-line entry point for the data generator.

Examples
--------
Small local sample:
    python -m generator.main --scale sample --output-dir data/sample

Generate and upload to the raw bucket:
    python -m generator.main --scale sample --output-dir data/sample \
        --gcs-uri gs://ecom-de-dev-3552-raw/ecommerce/batch_backfill

Parallel workers (each worker takes every N-th month):
    python -m generator.main --scale large --shard-index 3 --shard-count 10 ...
On Cloud Run Jobs the shard arguments default to CLOUD_RUN_TASK_INDEX/COUNT.
"""
import argparse
import logging
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from generator.calendar_patterns import month_starts, month_weight
from generator.config import HISTORY_END, HISTORY_START, MASTER_SEED, SCALES
from generator.customers import generate_customers
from generator.orders import generate_month
from generator.products import generate_products
from generator.quality_issues import inject_order_issues
from generator.writer import upload_to_gcs, write_csv

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger("generator")


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate synthetic e-commerce history.")
    parser.add_argument("--scale", choices=SCALES, default="sample")
    parser.add_argument("--output-dir", default="data/sample", help="Local folder for CSV files")
    parser.add_argument("--gcs-uri", default=None, help="Optional gs://bucket/prefix to upload to")
    parser.add_argument("--shard-index", type=int, default=int(os.getenv("CLOUD_RUN_TASK_INDEX", 0)))
    parser.add_argument("--shard-count", type=int, default=int(os.getenv("CLOUD_RUN_TASK_COUNT", 1)))
    return parser.parse_args(argv)


def orders_per_month(total_orders: int, months: list) -> list[int]:
    """Split the total order count across months in proportion to month weights."""
    weights = np.array([month_weight(m) for m in months])
    return [int(round(total_orders * w / weights.sum())) for w in weights]


def run(args: argparse.Namespace) -> list[Path]:
    scale = SCALES[args.scale]
    out = Path(args.output_dir)
    started = time.time()
    written: list[Path] = []

    # Master data is regenerated identically by every worker (same seed), so workers
    # never need to share files. Only shard 0 writes it out.
    customers, lifecycle = generate_customers(
        scale.n_customers, np.random.default_rng([MASTER_SEED, 0]), MASTER_SEED
    )
    products, popularity = generate_products(scale.n_products, np.random.default_rng([MASTER_SEED, 1]))

    if args.shard_index == 0:
        written.append(write_csv(customers, out / "customers" / "customers.csv"))
        written.append(write_csv(products, out / "products" / "products.csv"))
        truth = lifecycle[["customer_id", "signup_date", "churn_date"]]
        written.append(write_csv(truth, out / "_ground_truth" / "customer_lifecycle.csv"))

    months = month_starts(HISTORY_START, HISTORY_END)
    counts = orders_per_month(scale.n_orders, months)

    for month_index, (month_start, n_orders) in enumerate(zip(months, counts)):
        if month_index % args.shard_count != args.shard_index:
            continue  # another worker owns this month
        rng = np.random.default_rng([MASTER_SEED, 2, month_index])
        orders, items, labels = generate_month(
            month_index, month_start, n_orders, customers, lifecycle, products, popularity, rng
        )
        orders = inject_order_issues(orders, scale.n_customers, rng)

        tag = month_start.strftime("%Y-%m")
        part = f"order_month={tag}"
        written.append(write_csv(orders, out / "orders" / part / f"orders-{tag}.csv"))
        written.append(write_csv(items, out / "order_items" / part / f"order_items-{tag}.csv"))
        written.append(write_csv(labels, out / "_ground_truth" / "fraud_labels" / part / f"labels-{tag}.csv"))

    logger.info("Generated %d files in %.1fs", len(written), time.time() - started)

    if args.gcs_uri:
        upload_to_gcs(out, args.gcs_uri, written)
    return written


def main(argv=None) -> int:
    try:
        run(parse_args(argv))
        return 0
    except Exception:  # log the full traceback, exit non-zero so schedulers see the failure
        logger.exception("Generation failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
