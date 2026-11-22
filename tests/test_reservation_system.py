"""
Comprehensive Test Suite for Restaurant Table Reservation System.
Tests MongoDB connection, JSON Schema validation enforcement, CRUD operations,
double-booking interval overlap prevention, date-range queries, and aggregation pipelines.

Usage:
    python tests/test_reservation_system.py
    or:
    python -m unittest tests/test_reservation_system.py
"""

import sys
import os
import unittest
from datetime import datetime, timedelta, timezone
from bson import ObjectId
from pymongo.errors import WriteError

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import Config
from database import (
    get_db,
    get_mongo_client,
    get_reservations_collection,
    check_connection,
)
from services.reservation_service import (
    ReservationService,
    DoubleBookingError,
    ValidationError,
    ReservationError,
)
from scripts.init_db import initialize_database


class TestRestaurantReservationSystem(unittest.TestCase):
    """Test suite executing real operations against MongoDB restaurant_db."""

    @classmethod
    def setUpClass(cls):
        """Ensure database schema and indexes are initialized before running tests."""
        print("\n[Setup] Initializing database and ensuring indexes...")
        initialize_database()
        cls.collection = get_reservations_collection()
        cls.test_email = "tester.autounit@restaurant-test.com"

    def tearDown(self):
        """Clean up test reservations created during individual test methods."""
        self.collection.delete_many({"customer_email": {"$regex": "@restaurant-test\\.com$"}})

    # --------------------------------------------------------------------------
    # 1. Connection & Index Inspection Tests
    # --------------------------------------------------------------------------
    def test_01_mongodb_connection_and_ping(self):
        """Verify MongoDB ping command and connection health."""
        status = check_connection()
        self.assertTrue(status["connected"], f"MongoDB connection failed: {status.get('error')}")
        self.assertEqual(status["database"], "restaurant_db")
        print(f" -> Connected to MongoDB version: {status.get('version')}")

    def test_02_indexes_exist(self):
        """Inspect and verify that required compound and single indexes exist."""
        indexes = self.collection.index_information()
        expected_indexes = [
            "_id_",
            "idx_table_time",
            "idx_reservation_time",
            "idx_customer_email",
            "idx_status",
        ]
        for idx in expected_indexes:
            self.assertIn(idx, indexes, f"Expected index '{idx}' not found in {list(indexes.keys())}")
        
        # Check compound index keys
        table_time_key = indexes["idx_table_time"]["key"]
        self.assertEqual(table_time_key, [("table_number", 1), ("reservation_time", 1)])
        print(f" -> All expected indexes verified: {list(indexes.keys())}")

    # --------------------------------------------------------------------------
    # 2. Schema Validation Tests
    # --------------------------------------------------------------------------
    def test_03_schema_validation_rejects_missing_fields(self):
        """Verify MongoDB JSON Schema rejects documents with missing required fields."""
        invalid_doc = {
            "customer_name": "Incomplete Customer",
            # Missing customer_email, customer_phone, table_number, guests, reservation_time, status
        }
        with self.assertRaises(WriteError):
            self.collection.insert_one(invalid_doc)
        print(" -> MongoDB rejected document missing required fields as expected.")

    def test_04_schema_validation_rejects_negative_guests_and_tables(self):
        """Verify MongoDB JSON Schema enforces positive numbers for guests and table numbers."""
        invalid_doc = {
            "customer_name": "Negative Test",
            "customer_email": "tester.negative@restaurant-test.com",
            "customer_phone": "+1-555-9999",
            "table_number": -5,  # Illegal: negative table
            "guests": 0,         # Illegal: minimum is 1
            "reservation_time": datetime.now(timezone.utc),
            "status": "confirmed",
        }
        with self.assertRaises(WriteError):
            self.collection.insert_one(invalid_doc)
        print(" -> MongoDB rejected negative table_number and zero guests as expected.")

    def test_05_schema_validation_rejects_invalid_status(self):
        """Verify MongoDB JSON Schema enforces enum of allowed statuses."""
        invalid_doc = {
            "customer_name": "Enum Test",
            "customer_email": "tester.enum@restaurant-test.com",
            "customer_phone": "+1-555-8888",
            "table_number": 2,
            "guests": 2,
            "reservation_time": datetime.now(timezone.utc),
            "status": "not_an_allowed_status_xyz",  # Illegal status
        }
        with self.assertRaises(WriteError):
            self.collection.insert_one(invalid_doc)
        print(" -> MongoDB rejected invalid status enum as expected.")

    # --------------------------------------------------------------------------
    # 3. CRUD: insert_one, find_one, find, update_one
    # --------------------------------------------------------------------------
    def test_06_crud_insert_and_find(self):
        """Test insert_one() and retrieval using find_one() and find()."""
        future_time = datetime.now(timezone.utc) + timedelta(days=20, hours=19)
        payload = {
            "customer_name": "Alice Wonderland",
            "customer_email": "alice.w@restaurant-test.com",
            "customer_phone": "+1-555-1234",
            "table_number": 9,
            "guests": 4,
            "reservation_time": future_time.isoformat(),
            "duration_minutes": 90,
            "special_requests": "Window booth preferred",
            "status": "confirmed",
        }
        created = ReservationService.create_reservation(payload)
        self.assertIsNotNone(created.get("_id"))
        self.assertEqual(created["customer_name"], "Alice Wonderland")
        self.assertEqual(created["table_number"], 9)
        self.assertEqual(created["guests"], 4)

        # Retrieve using find_one() via Service
        fetched = ReservationService.get_reservation_by_id(created["_id"])
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["customer_email"], "alice.w@restaurant-test.com")

        # Retrieve using find() with filters
        results = ReservationService.list_reservations(status="confirmed", table_number=9)
        found = any(r["_id"] == created["_id"] for r in results)
        self.assertTrue(found, "Created reservation should be in filtered list results.")
        print(f" -> CRUD insert_one and find verified for ID: {created['_id']}")

    def test_07_crud_update_one(self):
        """Test update_one() updating guests, table, and special requests."""
        future_time = datetime.now(timezone.utc) + timedelta(days=21, hours=18)
        created = ReservationService.create_reservation({
            "customer_name": "Bob Builder",
            "customer_email": "bob.b@restaurant-test.com",
            "customer_phone": "+1-555-4321",
            "table_number": 10,
            "guests": 2,
            "reservation_time": future_time.isoformat(),
            "status": "confirmed",
        })

        # Update reservation
        updated = ReservationService.update_reservation(
            created["_id"],
            {
                "guests": 5,
                "special_requests": "Upgraded to 5 guests; birthday dinner",
            },
        )
        self.assertEqual(updated["guests"], 5)
        self.assertIn("birthday dinner", updated["special_requests"])

        # Confirm from DB directly
        in_db = self.collection.find_one({"_id": ObjectId(created["_id"])})
        self.assertEqual(in_db["guests"], 5)
        print(" -> CRUD update_one verified successfully.")

    # --------------------------------------------------------------------------
    # 4. Double-Booking Prevention & Concurrency Overlap Logic
    # --------------------------------------------------------------------------
    def test_08_double_booking_prevention(self):
        """
        Verify that overlapping reservations on the same table are strictly blocked.
        Interval: [19:00, 20:30]
        Overlap 1: [19:30, 21:00] (conflicts)
        Overlap 2: [18:30, 19:15] (conflicts)
        No Overlap: [20:30, 22:00] (succeeds)
        Different Table: [19:00, 20:30] on Table 12 (succeeds)
        """
        booking_day = datetime.now(timezone.utc) + timedelta(days=22)
        base_slot = datetime(booking_day.year, booking_day.month, booking_day.day, 19, 0, 0, tzinfo=timezone.utc)

        # Step 1: Initial reservation on Table 11 from 19:00 to 20:30 (90 min)
        first_booking = ReservationService.create_reservation({
            "customer_name": "Original Booker",
            "customer_email": "orig@restaurant-test.com",
            "customer_phone": "+1-555-1111",
            "table_number": 11,
            "guests": 2,
            "reservation_time": base_slot.isoformat(),
            "duration_minutes": 90,
            "status": "confirmed",
        })
        self.assertIsNotNone(first_booking["_id"])

        # Step 2: Attempt conflicting booking at 19:30 on same table (overlaps 19:00-20:30)
        overlap_slot_1 = base_slot + timedelta(minutes=30)
        with self.assertRaises(DoubleBookingError) as ctx:
            ReservationService.create_reservation({
                "customer_name": "Conflict Person 1",
                "customer_email": "conflict1@restaurant-test.com",
                "customer_phone": "+1-555-2222",
                "table_number": 11,
                "guests": 2,
                "reservation_time": overlap_slot_1.isoformat(),
                "duration_minutes": 90,
                "status": "confirmed",
            })
        self.assertIn("Double-booking conflict", str(ctx.exception))
        print(" -> Conflicting overlap at 19:30 successfully prevented.")

        # Step 3: Attempt conflicting booking at 18:30 with 90 min duration (ends at 20:00, overlaps)
        overlap_slot_2 = base_slot - timedelta(minutes=30)
        with self.assertRaises(DoubleBookingError) as ctx2:
            ReservationService.create_reservation({
                "customer_name": "Conflict Person 2",
                "customer_email": "conflict2@restaurant-test.com",
                "customer_phone": "+1-555-3333",
                "table_number": 11,
                "guests": 2,
                "reservation_time": overlap_slot_2.isoformat(),
                "duration_minutes": 90,
                "status": "confirmed",
            })
        self.assertIn("Double-booking conflict", str(ctx2.exception))
        print(" -> Conflicting overlap at 18:30 successfully prevented.")

        # Step 4: Non-overlapping booking at 20:30 on Table 11 should succeed
        non_overlap_slot = base_slot + timedelta(minutes=90)
        second_booking = ReservationService.create_reservation({
            "customer_name": "Subsequent Booker",
            "customer_email": "subsequent@restaurant-test.com",
            "customer_phone": "+1-555-4444",
            "table_number": 11,
            "guests": 4,
            "reservation_time": non_overlap_slot.isoformat(),
            "duration_minutes": 90,
            "status": "confirmed",
        })
        self.assertIsNotNone(second_booking["_id"])
        print(" -> Non-overlapping booking at 20:30 on same table successfully allowed.")

        # Step 5: Same time slot on a different table (Table 12) should succeed
        diff_table_booking = ReservationService.create_reservation({
            "customer_name": "Different Table Booker",
            "customer_email": "difftable@restaurant-test.com",
            "customer_phone": "+1-555-5555",
            "table_number": 12,
            "guests": 2,
            "reservation_time": base_slot.isoformat(),
            "duration_minutes": 90,
            "status": "confirmed",
        })
        self.assertIsNotNone(diff_table_booking["_id"])
        print(" -> Same time slot on different table (Table 12) successfully allowed.")

    # --------------------------------------------------------------------------
    # 5. Cancellation (Soft Delete) & Hard Delete
    # --------------------------------------------------------------------------
    def test_09_cancellation_frees_table(self):
        """
        Test that cancelling a reservation (soft-delete) changes status to 'cancelled'
        and immediately frees the table for another booking at the same time.
        """
        slot = datetime.now(timezone.utc) + timedelta(days=23, hours=19)
        first = ReservationService.create_reservation({
            "customer_name": "Will Cancel",
            "customer_email": "willcancel@restaurant-test.com",
            "customer_phone": "+1-555-6666",
            "table_number": 13,
            "guests": 2,
            "reservation_time": slot.isoformat(),
            "status": "confirmed",
        })

        # Cancel the reservation
        cancelled = ReservationService.cancel_reservation(first["_id"], reason="Customer called to cancel")
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertIn("Customer called to cancel", cancelled["special_requests"])

        # Now booking the exact same table and time slot must succeed!
        replacement = ReservationService.create_reservation({
            "customer_name": "Lucky New Booker",
            "customer_email": "luckynew@restaurant-test.com",
            "customer_phone": "+1-555-7777",
            "table_number": 13,
            "guests": 3,
            "reservation_time": slot.isoformat(),
            "status": "confirmed",
        })
        self.assertIsNotNone(replacement["_id"])
        self.assertEqual(replacement["status"], "confirmed")
        print(" -> Cancellation successfully freed table for new reservation.")

    def test_10_hard_delete(self):
        """Verify delete_one() permanently removes record."""
        slot = datetime.now(timezone.utc) + timedelta(days=24)
        created = ReservationService.create_reservation({
            "customer_name": "Hard Delete Me",
            "customer_email": "delete.me@restaurant-test.com",
            "customer_phone": "+1-555-8888",
            "table_number": 14,
            "guests": 2,
            "reservation_time": slot.isoformat(),
            "status": "confirmed",
        })
        res_id = created["_id"]
        deleted = ReservationService.delete_reservation(res_id)
        self.assertTrue(deleted)
        # Verify not found in DB
        self.assertIsNone(self.collection.find_one({"_id": ObjectId(res_id)}))
        print(" -> Hard delete permanently removed document as expected.")

    # --------------------------------------------------------------------------
    # 6. Date Queries: $gte and $lt
    # --------------------------------------------------------------------------
    def test_11_date_range_queries(self):
        """Verify date filtering using BSON Date values with $gte and $lt."""
        target_day = datetime.now(timezone.utc) + timedelta(days=25)
        day_start = datetime(target_day.year, target_day.month, target_day.day, 0, 0, 0, tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)

        # Create 2 bookings on target day, and 1 booking after target day
        ReservationService.create_reservation({
            "customer_name": "Target Day 1",
            "customer_email": "target1@restaurant-test.com",
            "customer_phone": "+1-555-9001",
            "table_number": 1,
            "guests": 2,
            "reservation_time": (day_start + timedelta(hours=12)).isoformat(),
            "status": "confirmed",
        })
        ReservationService.create_reservation({
            "customer_name": "Target Day 2",
            "customer_email": "target2@restaurant-test.com",
            "customer_phone": "+1-555-9002",
            "table_number": 2,
            "guests": 4,
            "reservation_time": (day_start + timedelta(hours=19)).isoformat(),
            "status": "confirmed",
        })
        ReservationService.create_reservation({
            "customer_name": "Next Day Out of Range",
            "customer_email": "outofrange@restaurant-test.com",
            "customer_phone": "+1-555-9003",
            "table_number": 1,
            "guests": 2,
            "reservation_time": (day_end + timedelta(hours=5)).isoformat(),
            "status": "confirmed",
        })

        # Query using $gte day_start and $lt day_end
        results = ReservationService.list_reservations(
            start_date=day_start.isoformat(),
            end_date=day_end.isoformat(),
        )
        test_results = [r for r in results if "@restaurant-test.com" in r["customer_email"]]
        self.assertEqual(len(test_results), 2)
        emails = [r["customer_email"] for r in test_results]
        self.assertIn("target1@restaurant-test.com", emails)
        self.assertIn("target2@restaurant-test.com", emails)
        self.assertNotIn("outofrange@restaurant-test.com", emails)
        print(" -> Date range query using $gte and $lt successfully filtered exact 24h window.")

    # --------------------------------------------------------------------------
    # 7. Aggregation Pipelines: $group and $sort
    # --------------------------------------------------------------------------
    def test_12_aggregation_pipeline_status_summary(self):
        """Verify MongoDB aggregation pipeline grouping by status with $group and $sort."""
        summary = ReservationService.get_summary_by_status()
        self.assertIsInstance(summary, list)
        self.assertTrue(len(summary) > 0, "Aggregation should return status summaries.")
        for item in summary:
            self.assertIn("status", item)
            self.assertIn("booking_count", item)
            self.assertIn("total_guests", item)
            self.assertGreaterEqual(item["booking_count"], 1)
        # Verify sorted descending by booking_count
        counts = [item["booking_count"] for item in summary]
        self.assertEqual(counts, sorted(counts, reverse=True), "Results must be sorted descending by count.")
        print(f" -> Aggregation by status pipeline verified: {summary[:3]}")

    def test_13_aggregation_pipeline_table_summary(self):
        """Verify MongoDB aggregation pipeline grouping by table with $group and $sort."""
        summary = ReservationService.get_summary_by_table()
        self.assertIsInstance(summary, list)
        self.assertTrue(len(summary) > 0, "Aggregation should return table summaries.")
        for item in summary:
            self.assertIn("table_number", item)
            self.assertIn("booking_count", item)
            self.assertIn("total_guests", item)
        # Verify sorted ascending by table_number
        tables = [item["table_number"] for item in summary]
        self.assertEqual(tables, sorted(tables), "Results must be sorted ascending by table_number.")
        print(f" -> Aggregation by table pipeline verified: {summary[:3]}")


if __name__ == "__main__":
    unittest.main(verbosity=2)

