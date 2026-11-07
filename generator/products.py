"""Generate the product catalog and its popularity distribution."""
import numpy as np
import pandas as pd

# category: (brands, median price in INR, price spread)
CATEGORIES = {
    "Electronics": (["Zentra", "Voltix", "Nexa", "Orbit"], 15_000, 0.9),
    "Fashion": (["Urbane", "Kurtaa", "Denimco", "Silkline"], 1_500, 0.6),
    "Home & Kitchen": (["HomeNest", "Cookwise", "Lumora"], 2_000, 0.7),
    "Books": (["PageTurn", "InkWell"], 400, 0.4),
    "Beauty": (["Glowup", "Herbalia", "Velvet"], 700, 0.5),
    "Sports": (["Stride", "PeakFit", "Racquetry"], 2_500, 0.8),
    "Grocery": (["FarmFresh", "DailyBasket"], 300, 0.5),
    "Toys": (["PlayNest", "BrickWorld"], 1_200, 0.6),
}
ADJECTIVES = ["Classic", "Pro", "Lite", "Max", "Eco", "Smart", "Ultra", "Prime", "Mini", "Plus"]


def generate_products(n_products: int, rng: np.random.Generator):
    """Return (products_df, popularity).

    popularity[i] is the probability that a purchased item is product i.
    It follows a Zipf-like (power-law) distribution: a few hit products dominate sales.
    """
    ids = np.arange(1, n_products + 1)
    category_names = np.array(list(CATEGORIES))
    category_idx = rng.integers(0, len(category_names), n_products)
    categories = category_names[category_idx]

    brands, prices, names = [], [], []
    for pid, cat in zip(ids, categories):
        cat_brands, median, spread = CATEGORIES[cat]
        brand = cat_brands[pid % len(cat_brands)]
        brands.append(brand)
        prices.append(round(float(rng.lognormal(np.log(median), spread)), 2))
        names.append(f"{brand} {ADJECTIVES[pid % len(ADJECTIVES)]} {cat.split()[0]} {pid}")

    products = pd.DataFrame({
        "product_id": ids,
        "sku": [f"SKU-{pid:07d}" for pid in ids],
        "product_name": names,
        "category": categories,
        "brand": brands,
        "list_price": prices,
        "currency": "INR",
    })

    # Power-law popularity, shuffled so popular products are spread across categories.
    ranks = rng.permutation(n_products) + 1
    popularity = 1.0 / ranks ** 1.1
    return products, popularity / popularity.sum()
