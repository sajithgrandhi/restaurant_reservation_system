"""
Database Initialization Script for Restaurant Table Reservation System.

Safely initializes the 'restaurant_db' database and 'reservations' collection:
1. Applies/Updates MongoDB JSON Schema Validation (without deleting documents).
2. Creates compound and single-field indexes for optimal query and scheduling performance.
3. Verifies and displays existing indexes.

Usage:
    python scripts/init_db.py
"""

import sys
import os
import logging
from pymongo import ASCENDING, DESCENDING

# Add parent directory to sys.path so config and database modules can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import Config
from database import get_db, get_mongo_client, RESERVATION_SCHEMA, sanitize_uri

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("init_db")


def initialize_database():
    """
    Safely initialize or update MongoDB schema validation and indexes.
    Idempotent: safe to run multiple times against fresh or existing databases.
    """
    logger.info("Connecting to MongoDB at: %s", sanitize_uri(Config.MONGO_URI))
    client = get_mongo_client()
    db = client[Config.MONGO_DB_NAME]

    # Verify server connectivity
    try:
        client.admin.command("ping")
        logger.info("Successfully connected to MongoDB server.")
    except Exception as exc:
        logger.error("Could not reach MongoDB server: %s", exc)
        sys.exit(1)

    existing_collections = db.list_collection_names()
    collection_name = "reservations"

    # Step 1: Create or Update Collection Schema Validation
    if collection_name not in existing_collections:
        logger.info("Collection '%s' does not exist. Creating with JSON Schema Validation...", collection_name)
        try:
            db.create_collection(
                collection_name,
                validator=RESERVATION_SCHEMA,
                validationAction="error",
                validationLevel="strict",
            )
            logger.info("Collection '%s' created successfully with strict schema validation.", collection_name)
        except Exception as exc:
            logger.error("Failed to create collection with validation: %s", exc)
            raise
    else:
        logger.info("Collection '%s' already exists. Updating JSON Schema Validator via collMod...", collection_name)
        try:
            db.command({
                "collMod": collection_name,
                "validator": RESERVATION_SCHEMA,
                "validationAction": "error",
                "validationLevel": "strict",
            })
            logger.info("Schema validator successfully updated via collMod without modifying existing documents.")
        except Exception as exc:
            logger.error("Failed to update schema validator: %s", exc)
            raise

    collection = db[collection_name]

    # Step 2: Create Required Indexes
    # Index 1: Compound index on table_number + reservation_time for schedule & overlap queries
    logger.info("Creating index: idx_table_time on (table_number: 1, reservation_time: 1)...")
    idx_table_time = collection.create_index(
        [("table_number", ASCENDING), ("reservation_time", ASCENDING)],
        name="idx_table_time",
    )
    logger.info("Created / verified index: %s", idx_table_time)

    # Index 2: Index on reservation_time for date-range queries ($gte, $lt)
    logger.info("Creating index: idx_reservation_time on (reservation_time: 1)...")
    idx_res_time = collection.create_index(
        [("reservation_time", ASCENDING)],
        name="idx_reservation_time",
    )
    logger.info("Created / verified index: %s", idx_res_time)

    # Index 3: Index on customer_email for fast customer lookup
    logger.info("Creating index: idx_customer_email on (customer_email: 1)...")
    idx_email = collection.create_index(
        [("customer_email", ASCENDING)],
        name="idx_customer_email",
    )
    logger.info("Created / verified index: %s", idx_email)

    # Index 4: Index on status for status filtering and active reservations
    logger.info("Creating index: idx_status on (status: 1)...")
    idx_status = collection.create_index(
        [("status", ASCENDING)],
        name="idx_status",
    )
    logger.info("Created / verified index: %s", idx_status)

    # Step 3: Inspect and verify all indexes
    logger.info("\n--- Current Indexes on '%s' ---", collection_name)
    indexes = collection.index_information()
    for name, details in indexes.items():
        keys = details.get("key", [])
        unique = details.get("unique", False)
        logger.info("  * Index '%s': keys=%s, unique=%s", name, keys, unique)

    doc_count = collection.count_documents({})
    logger.info("\nInitialization complete! Current document count in '%s': %d", collection_name, doc_count)
    return True


if __name__ == "__main__":
    initialize_database()

