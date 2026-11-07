"""Scale presets and global settings for the data generator.

Everything that controls *how much* data is generated lives here, so the same
code can produce a tiny sample on a laptop or the full "large" dataset in the cloud.
"""
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ScaleConfig:
    """How much data to generate."""

    name: str
    n_customers: int
    n_products: int
    n_orders: int  # total orders across the whole history (approximate)


SCALES = {
    # For development and unit tests: runs in seconds.
    "sample": ScaleConfig("sample", n_customers=5_000, n_products=1_000, n_orders=50_000),
    # Medium: a few minutes locally.
    "medium": ScaleConfig("medium", n_customers=100_000, n_products=10_000, n_orders=2_000_000),
    # Large: our target. Meant to run in the cloud with parallel workers.
    "large": ScaleConfig("large", n_customers=500_000, n_products=50_000, n_orders=20_000_000),
}

# Order history covered by the batch backfill. Cloud SQL + CDC take over after this.
HISTORY_START = date(2023, 1, 1)
HISTORY_END = date(2026, 9, 30)

# From this month onward, order files contain an extra column (schema evolution).
COUPON_COLUMN_FROM = date(2025, 7, 1)

# Master seed. Same seed + same scale = byte-identical output (reproducible runs).
MASTER_SEED = 42

# Fractions of deliberate data-quality problems (applied to order rows).
DQ_RATES = {
    "duplicate_rows": 0.003,      # exact duplicate rows
    "null_customer_id": 0.0005,   # missing foreign key
    "orphan_customer_id": 0.0002, # foreign key that points to no customer
    "alt_timestamp_format": 0.02, # DD/MM/YYYY instead of ISO
    "messy_case": 0.05,           # 'delivered' / 'Delivered' instead of 'DELIVERED'
}

FRAUD_RATE = 0.003  # share of orders that are fraudulent (hidden ground-truth label)
CHURN_RATE = 0.30   # share of customers who eventually stop buying
