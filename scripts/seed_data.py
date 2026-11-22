"""
Sample Data Seeding Script for Restaurant Table Reservation System.

Inserts fictional reservations for testing across various dates, tables,
party sizes, and reservation statuses.

Idempotency:
Checks for existing records by (customer_email, reservation_time) before inserting.
Running this script multiple times will NEVER produce duplicate records.

Usage:
    python scripts/seed_data.py
"""

import sys
import os
import logging
from datetime import datetime, timedelta, timezone

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import Config
from database import get_reservations_collection, sanitize_uri

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_data")


def seed_sample_data():
    """Insert idempotent fictional reservations into MongoDB."""
    collection = get_reservations_collection()
    logger.info("Connecting to MongoDB collection '%s'...", collection.name)

    # Base reference time: today at 18:00 UTC
    now = datetime.now(timezone.utc)
    base_date = datetime(now.year, now.month, now.day, 18, 0, 0, tzinfo=timezone.utc)

    # Curated list of realistic sample reservations
    sample_records = [
        # Past completed reservations (Yesterday)
        {
            "customer_name": "Eleanor Vance",
            "customer_email": "eleanor.vance@example.com",
            "customer_phone": "+1-555-0101",
            "table_number": 1,
            "guests": 2,
            "reservation_time": base_date - timedelta(days=1, hours=1),
            "duration_minutes": 90,
            "special_requests": "Quiet corner table preferred",
            "status": "completed",
        },
        {
            "customer_name": "Marcus Aurelius",
            "customer_email": "marcus.a@example.com",
            "customer_phone": "+1-555-0102",
            "table_number": 3,
            "guests": 4,
            "reservation_time": base_date - timedelta(days=1),
            "duration_minutes": 120,
            "special_requests": "Business dinner, sommelier recommendation requested",
            "status": "completed",
        },
        # Today's reservations (Seated and Confirmed)
        {
            "customer_name": "Sophia Rodriguez",
            "customer_email": "sophia.rodriguez@example.com",
            "customer_phone": "+1-555-0103",
            "table_number": 2,
            "guests": 2,
            "reservation_time": base_date,
            "duration_minutes": 90,
            "special_requests": "Anniversary celebration - champagne on arrival",
            "status": "seated",
        },
        {
            "customer_name": "David Kim",
            "customer_email": "david.kim@example.com",
            "customer_phone": "+1-555-0104",
            "table_number": 4,
            "guests": 6,
            "reservation_time": base_date + timedelta(hours=1),
            "duration_minutes": 120,
            "special_requests": "Need high chair for a toddler",
            "status": "confirmed",
        },
        {
            "customer_name": "Chloe Bennett",
            "customer_email": "chloe.b@example.com",
            "customer_phone": "+1-555-0105",
            "table_number": 5,
            "guests": 3,
            "reservation_time": base_date + timedelta(hours=2),
            "duration_minutes": 90,
            "special_requests": "Gluten-free menu options requested",
            "status": "confirmed",
        },
        # Tomorrow's reservations
        {
            "customer_name": "Liam O'Connor",
            "customer_email": "liam.oconnor@example.com",
            "customer_phone": "+1-555-0106",
            "table_number": 1,
            "guests": 2,
            "reservation_time": base_date + timedelta(days=1),
            "duration_minutes": 90,
            "special_requests": "Window table if possible",
            "status": "confirmed",
        },
        {
            "customer_name": "Amina Al-Mansoor",
            "customer_email": "amina.m@example.com",
            "customer_phone": "+1-555-0107",
            "table_number": 6,
            "guests": 8,
            "reservation_time": base_date + timedelta(days=1, hours=1),
            "duration_minutes": 150,
            "special_requests": "Family birthday gathering, bringing outside cake",
            "status": "confirmed",
        },
        {
            "customer_name": "Julian Thorne",
            "customer_email": "julian.thorne@example.com",
            "customer_phone": "+1-555-0108",
            "table_number": 3,
            "guests": 4,
            "reservation_time": base_date + timedelta(days=1, hours=2),
            "duration_minutes": 90,
            "special_requests": "Cancelled due to travel changes",
            "status": "cancelled",
        },
        # Upcoming weekend reservations (+3 to +5 days)
        {
            "customer_name": "Emma Watson",
            "customer_email": "emma.watson@example.com",
            "customer_phone": "+1-555-0109",
            "table_number": 7,
            "guests": 4,
            "reservation_time": base_date + timedelta(days=3),
            "duration_minutes": 90,
            "special_requests": "Celebrating graduation",
            "status": "confirmed",
        },
        {
            "customer_name": "Rajesh Patel",
            "customer_email": "rajesh.patel@example.com",
            "customer_phone": "+1-555-0110",
            "table_number": 2,
            "guests": 2,
            "reservation_time": base_date + timedelta(days=4, hours=1),
            "duration_minutes": 90,
            "special_requests": "Strict vegetarian dietary requirement",
            "status": "confirmed",
        },
        {
            "customer_name": "Lucas Miller",
            "customer_email": "lucas.miller@example.com",
            "customer_phone": "+1-555-0111",
            "table_number": 8,
            "guests": 10,
            "reservation_time": base_date + timedelta(days=5),
            "duration_minutes": 180,
            "special_requests": "Company team milestone dinner",
            "status": "pending",
        },
    ]

    inserted_count = 0
    skipped_count = 0

    for sample in sample_records:
        # Check uniqueness by customer email and reservation time
        existing = collection.find_one({
            "customer_email": sample["customer_email"],
            "reservation_time": sample["reservation_time"],
        })

        if existing:
            skipped_count += 1
            logger.debug("Skipping existing record for %s at %s", sample["customer_email"], sample["reservation_time"])
        else:
            doc = dict(sample)
            doc["created_at"] = now
            doc["updated_at"] = now
            collection.insert_one(doc)
            inserted_count += 1
            logger.info("Inserted sample reservation: %s | Table %d | %s | Status: %s",
                        doc["customer_name"], doc["table_number"], doc["reservation_time"].isoformat(), doc["status"])

    total_in_db = collection.count_documents({})
    logger.info("\n--- Seed Data Summary ---")
    logger.info("New records inserted: %d", inserted_count)
    logger.info("Existing records skipped (avoided duplicates): %d", skipped_count)
    logger.info("Total documents now in 'reservations': %d", total_in_db)
    return {"inserted": inserted_count, "skipped": skipped_count, "total": total_in_db}


if __name__ == "__main__":
    seed_sample_data()

