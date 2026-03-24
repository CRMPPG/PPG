"""Generate sample CSV files for testing the pipeline."""

import csv
import random
from pathlib import Path


STREETS = [
    "Main St", "Oak Ave", "Elm Dr", "Pine Rd", "Maple Ln",
    "Cedar Ct", "Birch Blvd", "Walnut Way", "Cherry Pl", "Spruce Cir",
    "Washington St", "Lincoln Ave", "Jefferson Dr", "Adams Rd", "Madison Ln",
    "Park Ave", "Lake Dr", "Hill Rd", "River Ln", "Valley Ct",
]

CITIES = ["Springfield", "Riverside", "Fairview", "Georgetown", "Lakewood"]


def generate_sample_listings(filepath: str | Path, count: int = 50):
    """Generate a sample listings CSV."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Address", "City", "State", "Zip", "List Price", "Bedrooms",
            "Bathrooms", "SqFt", "Year Built", "Days on Market", "Status",
            "Parcel Number",
        ])
        for i in range(count):
            num = random.randint(100, 9999)
            street = random.choice(STREETS)
            city = random.choice(CITIES)
            base_price = random.randint(80, 500) * 1000
            # Some properties listed below market
            if random.random() < 0.3:
                base_price = int(base_price * random.uniform(0.4, 0.7))
            writer.writerow([
                f"{num} {street}",
                city,
                "IL",
                f"6{random.randint(2000, 2999)}",
                f"${base_price:,}",
                random.choice([2, 3, 3, 4, 4, 5]),
                random.choice([1, 1.5, 2, 2, 2.5, 3]),
                random.randint(800, 4000),
                random.randint(1940, 2020),
                random.randint(1, 400),
                random.choice(["Active", "Active", "Active", "Pending", "Withdrawn"]),
                f"12-{random.randint(100, 999)}-{random.randint(100, 999):03d}",
            ])


def generate_sample_assessor(filepath: str | Path, listing_path: str | Path):
    """Generate assessor CSV that partially overlaps with listings."""
    listing_path = Path(listing_path)
    filepath = Path(filepath)

    # Read listings to create matching assessor records
    with open(listing_path, newline="") as f:
        reader = csv.DictReader(f)
        listings = list(reader)

    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Parcel Number", "Situs Address", "City", "State",
            "Assessed Value", "Land Value", "Improvement Value",
            "Tax Amount", "Tax Year", "Delinquent", "Delinquent Amount",
            "Foreclosure", "Bank Owned", "Vacant", "Code Violations",
            "Owner Occupied",
        ])
        for listing in listings:
            assessed_val = random.randint(100, 600) * 1000
            delinquent = random.random() < 0.2
            foreclosure = random.random() < 0.1
            bank_owned = random.random() < 0.05
            vacant = random.random() < 0.15
            violations = random.choice([0, 0, 0, 0, 1, 2, 3, 5])

            writer.writerow([
                listing.get("Parcel Number", ""),
                listing.get("Address", ""),
                listing.get("City", ""),
                listing.get("State", "IL"),
                f"${assessed_val:,}",
                f"${int(assessed_val * 0.3):,}",
                f"${int(assessed_val * 0.7):,}",
                f"${random.randint(2000, 12000):,}",
                "2025",
                "Yes" if delinquent else "No",
                f"${random.randint(5000, 50000):,}" if delinquent else "$0",
                "Yes" if foreclosure else "No",
                "Yes" if bank_owned else "No",
                "Yes" if vacant else "No",
                str(violations),
                random.choice(["Yes", "No"]),
            ])


if __name__ == "__main__":
    print("Generating sample data...")
    generate_sample_listings("sample_listings.csv")
    generate_sample_assessor("sample_assessor.csv", "sample_listings.csv")
    print("Done! Created sample_listings.csv and sample_assessor.csv")
