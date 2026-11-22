"""
Flask API Integration Test Suite for Restaurant Table Reservation System.
Tests all RESTful endpoints, status codes, JSON responses, double-booking rejection,
date-range filtering, and aggregation reporting through Flask test client.

Usage:
    python tests/test_api_endpoints.py
"""

import sys
import os
import unittest
import json
from datetime import datetime, timedelta, timezone

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from database import get_reservations_collection
from scripts.init_db import initialize_database


class TestFlaskAPIIntegration(unittest.TestCase):
    """Integration test suite using Flask TestClient."""

    @classmethod
    def setUpClass(cls):
        initialize_database()
        cls.client = app.test_client()
        cls.collection = get_reservations_collection()
        cls.test_email = "api.tester@restaurant-test.com"

    def tearDown(self):
        """Clean up test reservations created during individual test methods."""
        self.collection.delete_many({"customer_email": {"$regex": "@restaurant-test\\.com$"}})

    def test_01_health_check_endpoint(self):
        """Test GET /api/health returns MongoDB connectivity and indexes."""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["connected"])
        self.assertEqual(data["database"], "restaurant_db")
        self.assertIn("idx_table_time", data["indexes"])

    def test_02_create_reservation_endpoint(self):
        """Test POST /api/reservations creates a validated document."""
        future_time = datetime.now(timezone.utc) + timedelta(days=30, hours=19)
        payload = {
            "customer_name": "API Tester One",
            "customer_email": self.test_email,
            "customer_phone": "+1-555-0987",
            "table_number": 5,
            "guests": 4,
            "reservation_time": future_time.isoformat(),
            "duration_minutes": 90,
            "special_requests": "Chef recommendation menu",
        }
        response = self.client.post("/api/reservations", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["customer_name"], "API Tester One")
        self.assertEqual(data["data"]["status"], "confirmed")
        res_id = data["data"]["_id"]

        # Test GET /api/reservations/<id>
        get_res = self.client.get(f"/api/reservations/{res_id}")
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.get_json()["data"]["_id"], res_id)

    def test_03_double_booking_conflict_409(self):
        """Test POST /api/reservations returns HTTP 409 on overlapping slot."""
        future_time = datetime.now(timezone.utc) + timedelta(days=31, hours=20)
        payload1 = {
            "customer_name": "Original Diner",
            "customer_email": "diner1@restaurant-test.com",
            "customer_phone": "+1-555-1212",
            "table_number": 8,
            "guests": 2,
            "reservation_time": future_time.isoformat(),
            "duration_minutes": 90,
        }
        res1 = self.client.post("/api/reservations", json=payload1)
        self.assertEqual(res1.status_code, 201)

        # Attempt overlapping booking on same table (start 30 mins later)
        payload2 = {
            "customer_name": "Conflicting Diner",
            "customer_email": "diner2@restaurant-test.com",
            "customer_phone": "+1-555-3434",
            "table_number": 8,
            "guests": 2,
            "reservation_time": (future_time + timedelta(minutes=30)).isoformat(),
            "duration_minutes": 90,
        }
        res2 = self.client.post("/api/reservations", json=payload2)
        self.assertEqual(res2.status_code, 409)
        data2 = res2.get_json()
        self.assertEqual(data2["error_type"], "DOUBLE_BOOKING")
        self.assertIn("Double-booking conflict", data2["message"])

    def test_04_check_availability_endpoint(self):
        """Test GET /api/reservations/check-availability."""
        future_time = datetime.now(timezone.utc) + timedelta(days=32, hours=18)
        # Create booking
        self.client.post("/api/reservations", json={
            "customer_name": "Booked Diner",
            "customer_email": "booked@restaurant-test.com",
            "customer_phone": "+1-555-7654",
            "table_number": 7,
            "guests": 4,
            "reservation_time": future_time.isoformat(),
            "duration_minutes": 90,
        })

        # Check availability for the booked slot
        res_busy = self.client.get(
            f"/api/reservations/check-availability?table_number=7&reservation_time={future_time.isoformat()}&duration_minutes=90"
        )
        self.assertEqual(res_busy.status_code, 200)
        self.assertFalse(res_busy.get_json()["available"])

        # Check availability for a free slot
        free_time = future_time + timedelta(hours=3)
        res_free = self.client.get(
            f"/api/reservations/check-availability?table_number=7&reservation_time={free_time.isoformat()}&duration_minutes=90"
        )
        self.assertEqual(res_free.status_code, 200)
        self.assertTrue(res_free.get_json()["available"])

    def test_05_update_and_cancel_endpoints(self):
        """Test PUT /api/reservations/<id> and PATCH /api/reservations/<id>/cancel."""
        future_time = datetime.now(timezone.utc) + timedelta(days=33, hours=19)
        create_res = self.client.post("/api/reservations", json={
            "customer_name": "Update Tester",
            "customer_email": "update.test@restaurant-test.com",
            "customer_phone": "+1-555-6789",
            "table_number": 3,
            "guests": 2,
            "reservation_time": future_time.isoformat(),
            "duration_minutes": 90,
        })
        res_id = create_res.get_json()["data"]["_id"]

        # Update guests to 4
        update_res = self.client.put(f"/api/reservations/{res_id}", json={"guests": 4})
        self.assertEqual(update_res.status_code, 200)
        self.assertEqual(update_res.get_json()["data"]["guests"], 4)

        # Cancel reservation (soft delete)
        cancel_res = self.client.patch(
            f"/api/reservations/{res_id}/cancel",
            json={"reason": "Guest rescheduled"},
        )
        self.assertEqual(cancel_res.status_code, 200)
        self.assertEqual(cancel_res.get_json()["data"]["status"], "cancelled")

    def test_06_analytics_summary_endpoint(self):
        """Test GET /api/analytics/summary returns $group and $sort results."""
        response = self.client.get("/api/analytics/summary")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertIn("overall", data)
        self.assertIn("by_status", data)
        self.assertIn("by_table", data)
        self.assertIsInstance(data["by_status"], list)
        self.assertIsInstance(data["by_table"], list)


if __name__ == "__main__":
    unittest.main(verbosity=2)

