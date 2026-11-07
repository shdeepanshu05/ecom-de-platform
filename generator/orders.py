"""Generate one month of orders, order items and hidden fraud labels."""
from datetime import date, timedelta

import numpy as np
import pandas as pd

from generator.calendar_patterns import day_probabilities
from generator.config import COUPON_COLUMN_FROM, FRAUD_RATE
from generator.customers import customer_weights_for_month

# Approximate INR per unit of foreign currency, used only to price international orders.
# Real daily rates arrive later from the exchange-rate API.
APPROX_INR_PER_UNIT = {"INR": 1.0, "USD": 83.0, "GBP": 105.0, "EUR": 90.0, "AED": 22.6}
COUNTRIES = np.array(["IN", "US", "GB", "DE", "AE", "NG", "RU", "BR"])
PAYMENT_METHODS = np.array(["UPI", "CARD", "COD", "NETBANKING", "WALLET"])
PAYMENT_WEIGHTS = np.array([0.45, 0.25, 0.15, 0.08, 0.07])
STATUSES = np.array(["DELIVERED", "CANCELLED", "RETURNED"])
STATUS_WEIGHTS = np.array([0.92, 0.05, 0.03])
# Orders peak in the evening (hour-of-day weights, 0-23).
HOUR_WEIGHTS = np.array([1, 0.6, 0.4, 0.3, 0.3, 0.5, 1, 2, 3, 4, 4, 4,
                         4.5, 4, 3.5, 3.5, 4, 5, 6, 7, 8, 7, 5, 2.5])


def month_end(month_start: date) -> date:
    """Last day of the month."""
    nxt = date(month_start.year + month_start.month // 12, month_start.month % 12 + 1, 1)
    return nxt - timedelta(days=1)


def generate_month(
    month_index: int,
    month_start: date,
    n_orders: int,
    customers: pd.DataFrame,
    lifecycle: pd.DataFrame,
    products: pd.DataFrame,
    popularity: np.ndarray,
    rng: np.random.Generator,
):
    """Return (orders_df, items_df, fraud_labels_df) for one month.

    order_id = (month_index + 1) * 100_000_000 + sequence. Every month owns its own
    ID range, so parallel workers never need to coordinate to keep IDs unique.
    """
    m_end = month_end(month_start)

    # ---- 1. Which customers order this month -----------------------------------
    weights = customer_weights_for_month(lifecycle, month_start, m_end)
    customer_ids = rng.choice(lifecycle["customer_id"].to_numpy(), size=n_orders, p=weights)

    # ---- 2. Fraud orders: mostly brand-new accounts -----------------------------
    is_fraud = rng.random(n_orders) < FRAUD_RATE
    new_accounts = lifecycle.loc[
        (lifecycle["signup_date"] >= pd.Timestamp(month_start))
        & (lifecycle["signup_date"] <= pd.Timestamp(m_end)),
        "customer_id",
    ].to_numpy()
    if len(new_accounts) and is_fraud.any():
        customer_ids[is_fraud] = rng.choice(new_accounts, is_fraud.sum())

    # ---- 3. When: day by calendar weights, hour by time-of-day weights ---------
    days, day_p = day_probabilities(month_start)
    day_idx = rng.choice(len(days), n_orders, p=day_p)
    hours = rng.choice(24, n_orders, p=HOUR_WEIGHTS / HOUR_WEIGHTS.sum())
    order_ts = (
        pd.to_datetime(np.array(days, dtype="datetime64[D]")[day_idx])
        + pd.to_timedelta(hours, unit="h")
        + pd.to_timedelta(rng.integers(0, 3600, n_orders), unit="s")
    )

    # ---- 4. Items per order -----------------------------------------------------
    items_per_order = 1 + rng.poisson(1.5, n_orders)
    items_per_order[is_fraud] = rng.integers(2, 7, is_fraud.sum())
    n_items = int(items_per_order.sum())
    order_pos = np.repeat(np.arange(n_orders), items_per_order)  # which order each item belongs to

    product_ids = rng.choice(products["product_id"].to_numpy(), n_items, p=popularity)
    quantity = np.where(rng.random(n_items) < 0.85, 1, rng.integers(2, 4, n_items))

    # Fraudsters buy expensive electronics in bulk.
    fraud_items = is_fraud[order_pos]
    if fraud_items.any():
        electronics = products[products["category"] == "Electronics"]
        expensive = electronics.loc[
            electronics["list_price"] >= electronics["list_price"].quantile(0.75), "product_id"
        ].to_numpy()
        product_ids[fraud_items] = rng.choice(expensive, fraud_items.sum())
        quantity[fraud_items] = rng.integers(1, 4, fraud_items.sum())

    # ---- 5. Prices in the customer's currency -----------------------------------
    list_price_inr = products["list_price"].to_numpy()[product_ids - 1]
    discount = rng.choice([0.0, 0.05, 0.10, 0.20], n_items, p=[0.6, 0.2, 0.15, 0.05])
    customer_currency = customers["preferred_currency"].to_numpy()[customer_ids - 1]
    item_currency = customer_currency[order_pos]
    fx = np.vectorize(APPROX_INR_PER_UNIT.get)(item_currency)
    unit_price = np.round(list_price_inr * (1 - discount) / fx, 2)
    line_total = np.round(unit_price * quantity, 2)
    order_total = np.round(np.bincount(order_pos, weights=line_total, minlength=n_orders), 2)

    # ---- 6. Shipping country, payment, status ----------------------------------
    home_country = lifecycle["country"].to_numpy()[customer_ids - 1]
    shipping_country = home_country.copy()
    shipping_country[is_fraud] = rng.choice(COUNTRIES, is_fraud.sum())  # often a mismatch
    payment = rng.choice(PAYMENT_METHODS, n_orders, p=PAYMENT_WEIGHTS)
    payment[home_country != "IN"] = "CARD"
    payment[is_fraud] = "CARD"
    status = rng.choice(STATUSES, n_orders, p=STATUS_WEIGHTS)

    base = (month_index + 1) * 100_000_000
    order_ids = base + np.arange(1, n_orders + 1)

    orders = pd.DataFrame({
        "order_id": order_ids,
        "customer_id": customer_ids,
        "order_ts": order_ts,
        "status": status,
        "currency": customer_currency,
        "payment_method": payment,
        "shipping_country": shipping_country,
        "item_count": items_per_order,
        "order_total": order_total,
    })
    # Schema evolution: newer exports have an extra column at the end.
    if month_start >= COUPON_COLUMN_FROM:
        has_coupon = rng.random(n_orders) < 0.2
        codes = np.array(["SAVE10", "FEST20", "NEWUSER", "FLAT100"])
        orders["coupon_code"] = np.where(has_coupon, rng.choice(codes, n_orders), None)

    items = pd.DataFrame({
        "order_item_id": base * 10 + np.arange(1, n_items + 1),
        "order_id": order_ids[order_pos],
        "product_id": product_ids,
        "quantity": quantity,
        "unit_price": unit_price,
        "line_total": line_total,
    })
    labels = pd.DataFrame({"order_id": order_ids, "is_fraud": is_fraud})
    return orders, items, labels
