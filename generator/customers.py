"""Generate the customer master data and each customer's hidden lifecycle."""
from datetime import date, timedelta

import numpy as np
import pandas as pd
from faker import Faker

from generator.config import CHURN_RATE, HISTORY_END, HISTORY_START

# (city, state, country, relative weight). Mostly Indian customers, some international.
CITIES = [
    ("Mumbai", "Maharashtra", "IN", 14), ("Delhi", "Delhi", "IN", 14),
    ("Bengaluru", "Karnataka", "IN", 12), ("Pune", "Maharashtra", "IN", 8),
    ("Hyderabad", "Telangana", "IN", 9), ("Chennai", "Tamil Nadu", "IN", 8),
    ("Kolkata", "West Bengal", "IN", 7), ("Ahmedabad", "Gujarat", "IN", 6),
    ("Jaipur", "Rajasthan", "IN", 4), ("Lucknow", "Uttar Pradesh", "IN", 4),
    ("Indore", "Madhya Pradesh", "IN", 3), ("Kochi", "Kerala", "IN", 3),
    ("New York", "NY", "US", 3), ("London", "England", "GB", 2),
    ("Berlin", "Berlin", "DE", 1), ("Dubai", "Dubai", "AE", 2),
]
CURRENCY_BY_COUNTRY = {"IN": "INR", "US": "USD", "GB": "GBP", "DE": "EUR", "AE": "AED"}


def generate_customers(n_customers: int, rng: np.random.Generator, seed: int):
    """Return (customers_df, lifecycle_df).

    customers_df is what the "source system" exports.
    lifecycle_df is hidden ground truth (activity level, churn date) used only
    to generate realistic orders and, later, to evaluate the churn model.
    """
    fake = Faker("en_IN")
    Faker.seed(seed)
    # Faker is slow per call, so build small pools once and sample from them with numpy.
    first_names = np.array([fake.first_name() for _ in range(500)])
    last_names = np.array([fake.last_name() for _ in range(500)])

    ids = np.arange(1, n_customers + 1)
    first = rng.choice(first_names, n_customers)
    last = rng.choice(last_names, n_customers)

    city_weights = np.array([c[3] for c in CITIES], dtype=float)
    city_idx = rng.choice(len(CITIES), n_customers, p=city_weights / city_weights.sum())
    cities = np.array([c[0] for c in CITIES])[city_idx]
    states = np.array([c[1] for c in CITIES])[city_idx]
    countries = np.array([c[2] for c in CITIES])[city_idx]

    # Some customers existed before the order history starts.
    signup_start = HISTORY_START - timedelta(days=730)
    span_days = (HISTORY_END - signup_start).days
    signup_offsets = rng.integers(0, span_days, n_customers)
    signup_dates = pd.to_datetime(signup_start) + pd.to_timedelta(signup_offsets, unit="D")
    signup_ts = signup_dates + pd.to_timedelta(rng.integers(0, 86_400, n_customers), unit="s")

    emails = [f"{f.lower()}.{l.lower()}{i}@example.com" for f, l, i in zip(first, last, ids)]
    phones = [f"+91{n}" for n in rng.integers(7_000_000_000, 9_999_999_999, n_customers)]

    customers = pd.DataFrame({
        "customer_id": ids,
        "first_name": first,
        "last_name": last,
        "email": emails,
        "phone": phones,
        "city": cities,
        "state": states,
        "country": countries,
        "preferred_currency": [CURRENCY_BY_COUNTRY[c] for c in countries],
        "signup_ts": signup_ts.strftime("%Y-%m-%dT%H:%M:%S"),
    })
    # Data-quality issue: ~1% of customers have no email.
    missing_email = rng.random(n_customers) < 0.01
    customers.loc[missing_email, "email"] = None

    # Hidden lifecycle: a few customers buy a lot, most buy rarely (log-normal activity).
    activity = rng.lognormal(mean=0.0, sigma=1.0, size=n_customers)
    churns = rng.random(n_customers) < CHURN_RATE
    # Churners stop buying 60 to 900 days after signing up.
    churn_offsets = rng.integers(60, 900, n_customers)
    churn_dates = signup_dates + pd.to_timedelta(churn_offsets, unit="D")
    lifecycle = pd.DataFrame({
        "customer_id": ids,
        "country": countries,
        "signup_date": signup_dates,
        "activity": activity,
        "churn_date": pd.Series(churn_dates).where(churns, pd.NaT).values,
    })
    return customers, lifecycle


def customer_weights_for_month(lifecycle: pd.DataFrame, month_start: date, month_end: date) -> np.ndarray:
    """Probability of each customer placing an order in this month.

    - not yet signed up  -> 0
    - already churned    -> 0
    - within 90 days before churn -> activity fades linearly (the churn signal)
    """
    start = pd.Timestamp(month_start)
    end = pd.Timestamp(month_end)
    weights = lifecycle["activity"].to_numpy().copy()
    weights[(lifecycle["signup_date"] > end).to_numpy()] = 0.0

    churn = lifecycle["churn_date"]
    has_churn = churn.notna().to_numpy()
    churned = has_churn & (churn <= start).fillna(False).to_numpy()
    weights[churned] = 0.0

    days_to_churn = (churn - start).dt.days.to_numpy()
    fading = has_churn & ~churned & (days_to_churn < 90)
    weights[fading] *= np.clip(days_to_churn[fading] / 90.0, 0.05, 1.0)

    total = weights.sum()
    return weights / total if total > 0 else weights
