"""Inject realistic data-quality problems into the orders export.

Clean synthetic data teaches nothing about cleaning. These defects are exactly
what the Silver layer (Phase 3) must detect and fix.
"""
import numpy as np
import pandas as pd

from generator.config import DQ_RATES


def inject_order_issues(orders: pd.DataFrame, n_customers: int, rng: np.random.Generator) -> pd.DataFrame:
    """Return a messy copy of orders with order_ts converted to text."""
    df = orders.copy()
    n = len(df)

    # 1. Timestamps as text: mostly ISO 8601, some in DD/MM/YYYY.
    iso = df["order_ts"].dt.strftime("%Y-%m-%dT%H:%M:%S")
    alt = df["order_ts"].dt.strftime("%d/%m/%Y %H:%M:%S")
    use_alt = rng.random(n) < DQ_RATES["alt_timestamp_format"]
    df["order_ts"] = np.where(use_alt, alt, iso)

    # 2. Inconsistent casing in categorical columns.
    messy = rng.random(n) < DQ_RATES["messy_case"]
    df.loc[messy, "status"] = df.loc[messy, "status"].str.lower()
    df.loc[messy, "currency"] = df.loc[messy, "currency"].str.lower()

    # 3. Broken foreign keys: missing, or pointing to a customer that doesn't exist.
    df["customer_id"] = df["customer_id"].astype("Int64")  # nullable integer
    null_fk = rng.random(n) < DQ_RATES["null_customer_id"]
    df.loc[null_fk, "customer_id"] = pd.NA
    orphan = rng.random(n) < DQ_RATES["orphan_customer_id"]
    df.loc[orphan, "customer_id"] = n_customers + rng.integers(1, 1_000_000, orphan.sum())

    # 4. Exact duplicate rows (e.g. an export retried), then shuffle row order.
    dupes = df.sample(frac=DQ_RATES["duplicate_rows"], random_state=int(rng.integers(1 << 31)))
    df = pd.concat([df, dupes], ignore_index=True)
    return df.sample(frac=1.0, random_state=int(rng.integers(1 << 31))).reset_index(drop=True)
