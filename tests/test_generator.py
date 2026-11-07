"""Unit tests for the synthetic data generator. Run with:  pytest -q"""
from datetime import date

import numpy as np
import pandas as pd
import pytest

from generator.calendar_patterns import day_weight, month_starts
from generator.config import COUPON_COLUMN_FROM, HISTORY_END, HISTORY_START, MASTER_SEED
from generator.customers import generate_customers
from generator.main import orders_per_month, parse_args, run
from generator.orders import generate_month
from generator.products import generate_products
from generator.quality_issues import inject_order_issues

N_CUSTOMERS, N_PRODUCTS = 2_000, 300


@pytest.fixture(scope="module")
def master_data():
    customers, lifecycle = generate_customers(N_CUSTOMERS, np.random.default_rng([MASTER_SEED, 0]), MASTER_SEED)
    products, popularity = generate_products(N_PRODUCTS, np.random.default_rng([MASTER_SEED, 1]))
    return customers, lifecycle, products, popularity


def make_month(master_data, month_index=0, month=date(2023, 1, 1), n=5_000, seed=7):
    customers, lifecycle, products, popularity = master_data
    return generate_month(month_index, month, n, customers, lifecycle, products, popularity,
                          np.random.default_rng(seed))


def test_same_seed_gives_identical_output(master_data):
    first, _, _ = make_month(master_data, seed=1)
    second, _, _ = make_month(master_data, seed=1)
    pd.testing.assert_frame_equal(first, second)


def test_order_ids_unique_and_months_do_not_overlap(master_data):
    jan, _, _ = make_month(master_data, month_index=0)
    feb, _, _ = make_month(master_data, month_index=1, month=date(2023, 2, 1))
    assert jan["order_id"].is_unique
    assert set(jan["order_id"]).isdisjoint(feb["order_id"])


def test_item_lines_add_up_to_order_total(master_data):
    orders, items, _ = make_month(master_data)
    totals = items.groupby("order_id")["line_total"].sum().round(2)
    merged = orders.set_index("order_id")["order_total"]
    assert np.allclose(totals.loc[merged.index], merged, atol=0.05)


def test_clean_orders_reference_existing_customers(master_data):
    orders, _, _ = make_month(master_data)
    assert orders["customer_id"].between(1, N_CUSTOMERS).all()


def test_no_orders_after_churn_or_before_signup(master_data):
    _, lifecycle, _, _ = master_data
    orders, _, _ = make_month(master_data, month=date(2025, 6, 1), month_index=29)
    joined = orders.merge(lifecycle, on="customer_id")
    month_start = pd.Timestamp("2025-06-01")
    assert (joined["signup_date"] <= pd.Timestamp("2025-06-30")).all()
    churned_before = joined["churn_date"].notna() & (joined["churn_date"] <= month_start)
    assert not churned_before.any()


def test_coupon_column_only_after_schema_change(master_data):
    old, _, _ = make_month(master_data, month=date(2025, 6, 1), month_index=29)
    new, _, _ = make_month(master_data, month=COUPON_COLUMN_FROM, month_index=30)
    assert "coupon_code" not in old.columns
    assert "coupon_code" in new.columns


def test_fraud_orders_are_larger_on_average(master_data):
    orders, _, labels = make_month(master_data, n=20_000)
    fraud = labels["is_fraud"].to_numpy()
    assert fraud.any()
    assert orders.loc[fraud, "order_total"].mean() > orders.loc[~fraud, "order_total"].mean()


def test_quality_issues_are_injected(master_data):
    orders, _, _ = make_month(master_data, n=20_000)
    messy = inject_order_issues(orders, N_CUSTOMERS, np.random.default_rng(3))
    assert len(messy) > len(orders)                         # duplicates added
    assert messy.duplicated().any()
    assert messy["customer_id"].isna().any()                # null foreign keys
    assert (messy["customer_id"] > N_CUSTOMERS).any()       # orphans
    assert messy["order_ts"].str.contains("/").any()        # DD/MM/YYYY format
    assert (messy["status"] == "delivered").any()           # lower-case values


def test_weekends_and_festivals_weigh_more():
    assert day_weight(date(2024, 6, 15)) > day_weight(date(2024, 6, 12))   # Sat vs Wed
    assert day_weight(date(2024, 10, 28)) > day_weight(date(2024, 10, 21))  # Diwali week


def test_month_counts_sum_to_total():
    months = month_starts(HISTORY_START, HISTORY_END)
    counts = orders_per_month(1_000_000, months)
    assert abs(sum(counts) - 1_000_000) <= len(months)


def test_shards_cover_every_month_exactly_once(tmp_path):
    files = []
    for shard in range(3):
        args = parse_args(["--scale", "sample", "--output-dir", str(tmp_path),
                           "--shard-index", str(shard), "--shard-count", "3"])
        files += [f for f in run(args) if f.parent.parent.name == "orders"]
    names = [f.name for f in files]
    assert len(names) == len(set(names)) == len(month_starts(HISTORY_START, HISTORY_END))
