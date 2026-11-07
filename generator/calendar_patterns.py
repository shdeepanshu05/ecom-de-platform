"""Calendar effects: which days get more orders.

Real sales are not uniform. Weekends, salary days and festivals produce spikes.
These weights decide how a month's orders are spread across its days.
"""
from datetime import date, timedelta

import numpy as np

# Approximate peak shopping windows (start date, number of days, multiplier).
FESTIVALS = [
    (date(2023, 11, 8), 7, 3.0),    # Diwali 2023 sales
    (date(2024, 10, 27), 7, 3.0),   # Diwali 2024 sales
    (date(2025, 10, 16), 7, 3.0),   # Diwali 2025 sales
    (date(2023, 11, 24), 4, 2.0),   # Black Friday weekends
    (date(2024, 11, 29), 4, 2.0),
    (date(2025, 11, 28), 4, 2.0),
]


def month_starts(start: date, end: date) -> list[date]:
    """Return the first day of every month between start and end (inclusive)."""
    months = []
    current = date(start.year, start.month, 1)
    while current <= end:
        months.append(current)
        current = date(current.year + current.month // 12, current.month % 12 + 1, 1)
    return months


def days_in_month(month_start: date) -> list[date]:
    """All calendar days of the month that starts at month_start."""
    nxt = date(month_start.year + month_start.month // 12, month_start.month % 12 + 1, 1)
    return [month_start + timedelta(days=i) for i in range((nxt - month_start).days)]


def day_weight(day: date) -> float:
    """Relative order volume for one day."""
    weight = 1.0
    if day.weekday() >= 5:      # Saturday or Sunday
        weight *= 1.3
    if day.day <= 5:            # salary days at the start of the month
        weight *= 1.2
    for festival_start, length, multiplier in FESTIVALS:
        if festival_start <= day < festival_start + timedelta(days=length):
            weight *= multiplier
    return weight


def month_weight(month_start: date) -> float:
    """Total relative volume of a month (sum of its day weights) with slow growth over time."""
    base = sum(day_weight(d) for d in days_in_month(month_start))
    months_since_2023 = (month_start.year - 2023) * 12 + month_start.month - 1
    growth = 1.015 ** months_since_2023  # business grows ~1.5% per month
    return base * growth


def day_probabilities(month_start: date) -> tuple[list[date], np.ndarray]:
    """Days of the month and the probability that an order falls on each one."""
    days = days_in_month(month_start)
    weights = np.array([day_weight(d) for d in days])
    return days, weights / weights.sum()
