"""Generate data/sample/sales.csv for the fictional brand "Frosty Scoops". Deterministic (seeded).

Planted patterns the assistant should be able to find (and that the sample documents explain):
- Mango Alphonso falls ~30% in the North in 2025 (new pulp supplier, see operations SOP + reviews)
- Sugar-Free Vanilla grows ~45% year on year
- Quick-commerce channel share grows through 2025
- Cookie Crunch launches in July 2024
- Strong summer (Apr–Jun) seasonality

Usage: python -m scripts.make_sample_data
"""
import csv
import random
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "sample" / "sales.csv"

REGIONS = {"North": 1.2, "South": 1.0, "East": 0.7, "West": 1.1}
FLAVOURS = {  # name: (price INR per 500ml tub in 2024, base monthly units per region/channel)
    "Vanilla": (180, 420), "Chocolate": (200, 400), "Mango Alphonso": (240, 300),
    "Butterscotch": (190, 280), "Strawberry": (190, 200), "Kesar Pista": (260, 180),
    "Cookie Crunch": (250, 220), "Sugar-Free Vanilla": (230, 90),
}
SEASON = {1: .6, 2: .7, 3: 1.0, 4: 1.4, 5: 1.6, 6: 1.4, 7: 1.0, 8: .9, 9: .9, 10: .85, 11: .7, 12: .65}


def channel_shares(year: int, month: int) -> dict[str, float]:
    qc = 0.18 + (0.17 * month / 12 if year == 2025 else 0)  # quick-commerce 18% → 35% over 2025
    return {"Parlour": 0.35, "Supermarket": 0.65 - qc, "Quick-commerce": qc}


def main() -> None:
    rng = random.Random(42)
    rows = []
    for year in (2024, 2025):
        for month in range(1, 13):
            for region, r_weight in REGIONS.items():
                for channel, share in channel_shares(year, month).items():
                    for flavour, (price, base) in FLAVOURS.items():
                        if flavour == "Cookie Crunch" and (year, month) < (2024, 7):
                            continue
                        f = SEASON[month] * r_weight * share * 3 * (1.08 if year == 2025 else 1)
                        if flavour == "Mango Alphonso":
                            f *= 1.6 if month in (4, 5, 6) else 0.6
                            if year == 2025:
                                f *= 0.70 if region == "North" else 0.92
                        if flavour == "Sugar-Free Vanilla" and year == 2025:
                            f *= 1.45
                        units = round(base * f * rng.uniform(0.9, 1.1))
                        unit_price = price * (1.05 if year == 2025 else 1)
                        rows.append([f"{year}-{month:02d}-01", region, channel, flavour, units,
                                     round(units * unit_price, 2)])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["month", "region", "channel", "flavour", "units_sold", "revenue_inr"])
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUT}")


if __name__ == "__main__":
    main()
