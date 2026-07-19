"""Seed script for IP geolocation and BIN lookup tables.

This script populates the lookup tables with sample data for testing.
In production, these would be populated from official IP allocation
registries and card network BIN databases.

Run: python scripts/seed_enrichment_data.py
"""

import sys
import os

from sqlalchemy.orm import Session

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from cruds import ip_geolocation_crud, bin_lookup_crud


# Sample IP geolocation data
# In production, this would come from MaxMind GeoLite2, IP2Location, or similar
SAMPLE_IP_GEOLOCATIONS = [
    # United States ranges
    {
        "ip_start": "1.0.0.0",
        "ip_end": "1.0.0.255",
        "country_code": "US",
        "region": "California",
        "city": "Los Angeles",
        "isp": "APNIC Research",
    },
    {
        "ip_start": "8.8.8.0",
        "ip_end": "8.8.8.255",
        "country_code": "US",
        "region": "California",
        "city": "Mountain View",
        "isp": "Google DNS",
    },
    {
        "ip_start": "52.0.0.0",
        "ip_end": "52.255.255.255",
        "country_code": "US",
        "region": "Virginia",
        "city": "Ashburn",
        "isp": "AWS",
    },
    # United Kingdom
    {
        "ip_start": "25.0.0.0",
        "ip_end": "25.255.255.255",
        "country_code": "GB",
        "region": "England",
        "city": "London",
        "isp": "UK MoD",
    },
    # Germany
    {
        "ip_start": "53.0.0.0",
        "ip_end": "53.255.255.255",
        "country_code": "DE",
        "region": "Bavaria",
        "city": "Munich",
        "isp": "Daimler",
    },
    # High-risk regions (for testing fraud detection)
    {
        "ip_start": "91.200.0.0",
        "ip_end": "91.200.255.255",
        "country_code": "RU",
        "region": "Moscow",
        "city": "Moscow",
        "isp": "Russian ISP",
    },
    {
        "ip_start": "197.0.0.0",
        "ip_end": "197.255.255.255",
        "country_code": "ZA",
        "region": "Gauteng",
        "city": "Johannesburg",
        "isp": "South African ISP",
    },
    # Anonymous/VPN ranges (commonly used for fraud)
    {
        "ip_start": "10.0.0.0",
        "ip_end": "10.255.255.255",
        "country_code": "XX",
        "region": "Private",
        "city": "Private",
        "isp": "Private RFC1918",
    },
    {
        "ip_start": "172.16.0.0",
        "ip_end": "172.31.255.255",
        "country_code": "XX",
        "region": "Private",
        "city": "Private",
        "isp": "Private RFC1918",
    },
    {
        "ip_start": "192.168.0.0",
        "ip_end": "192.168.255.255",
        "country_code": "XX",
        "region": "Private",
        "city": "Private",
        "isp": "Private RFC1918",
    },
]


# Sample BIN data
# In production, this would come from official card network BIN databases
SAMPLE_BINS = [
    # Visa
    {
        "bin_number": "411111",
        "card_brand": "visa",
        "card_type": "credit",
        "card_category": "Classic",
        "issuing_bank": "Chase",
        "issuing_country_code": "US",
        "issuing_country_name": "United States",
        "is_prepaid": False,
        "is_commercial": False,
        "risk_score": 10,
    },
    {
        "bin_number": "424242",
        "card_brand": "visa",
        "card_type": "credit",
        "card_category": "Platinum",
        "issuing_bank": "Bank of America",
        "issuing_country_code": "US",
        "issuing_country_name": "United States",
        "is_prepaid": False,
        "is_commercial": False,
        "risk_score": 15,
    },
    {
        "bin_number": "400000",
        "card_brand": "visa",
        "card_type": "debit",
        "card_category": "Classic",
        "issuing_bank": "Wells Fargo",
        "issuing_country_code": "US",
        "issuing_country_name": "United States",
        "is_prepaid": False,
        "is_commercial": False,
        "risk_score": 20,
    },
    # Mastercard
    {
        "bin_number": "510000",
        "card_brand": "mastercard",
        "card_type": "credit",
        "card_category": "World",
        "issuing_bank": "Citi",
        "issuing_country_code": "US",
        "issuing_country_name": "United States",
        "is_prepaid": False,
        "is_commercial": False,
        "risk_score": 15,
    },
    {
        "bin_number": "520000",
        "card_brand": "mastercard",
        "card_type": "debit",
        "card_category": "Standard",
        "issuing_bank": "Capital One",
        "issuing_country_code": "US",
        "issuing_country_name": "United States",
        "is_prepaid": False,
        "is_commercial": False,
        "risk_score": 25,
    },
    # High-risk BINs (prepaid/gift cards commonly used for fraud)
    {
        "bin_number": "601100",
        "card_brand": "discover",
        "card_type": "prepaid",
        "card_category": "Gift",
        "issuing_bank": "Green Dot",
        "issuing_country_code": "US",
        "issuing_country_name": "United States",
        "is_prepaid": True,
        "is_commercial": False,
        "risk_score": 75,
    },
    {
        "bin_number": "371449",
        "card_brand": "amex",
        "card_type": "prepaid",
        "card_category": "Serve",
        "issuing_bank": "American Express",
        "issuing_country_code": "US",
        "issuing_country_name": "United States",
        "is_prepaid": True,
        "is_commercial": False,
        "risk_score": 70,
    },
    # International BINs (higher risk for cross-border fraud)
    {
        "bin_number": "400012",
        "card_brand": "visa",
        "card_type": "credit",
        "card_category": "Classic",
        "issuing_bank": "Barclays",
        "issuing_country_code": "GB",
        "issuing_country_name": "United Kingdom",
        "is_prepaid": False,
        "is_commercial": False,
        "risk_score": 30,
    },
    {
        "bin_number": "510510",
        "card_brand": "mastercard",
        "card_type": "credit",
        "card_category": "World",
        "issuing_bank": "Deutsche Bank",
        "issuing_country_code": "DE",
        "issuing_country_name": "Germany",
        "is_prepaid": False,
        "is_commercial": False,
        "risk_score": 35,
    },
]


def seed_ip_geolocations(db: Session) -> int:
    """Seed IP geolocation data."""
    count = 0
    for data in SAMPLE_IP_GEOLOCATIONS:
        # Check if already exists
        existing = ip_geolocation_crud.get_geolocation_by_ip(db, data["ip_start"])
        if existing:
            continue

        ip_geolocation_crud.create_ip_geolocation(db, **data)
        count += 1

    return count


def seed_bin_lookups(db: Session) -> int:
    """Seed BIN lookup data."""
    count = 0
    for data in SAMPLE_BINS:
        # Check if already exists
        existing = bin_lookup_crud.get_bin_by_number(db, data["bin_number"])
        if existing:
            continue

        bin_lookup_crud.create_bin_lookup(db, **data)
        count += 1

    return count


def main():
    """Main seeding function."""
    print("Using existing migrated database schema...")

    db = SessionLocal()
    try:
        print("Seeding IP geolocation data...")
        ip_count = seed_ip_geolocations(db)
        print(f"  Created {ip_count} IP geolocation entries")

        print("Seeding BIN lookup data...")
        bin_count = seed_bin_lookups(db)
        print(f"  Created {bin_count} BIN lookup entries")

        print("\nSeeding complete!")
        print(f"Total: {ip_count + bin_count} records created")

    except Exception as e:
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
