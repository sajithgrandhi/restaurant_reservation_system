"""
Reservation Service Module.
Encapsulates all database operations, business logic, MongoDB query builders,
double-booking overlap detection, and aggregation pipelines.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import WriteError, DuplicateKeyError

from config import Config
from database import get_reservations_collection, serialize_document, serialize_documents


class ReservationError(Exception):
    """Custom domain exception for reservation business logic errors."""
    pass


class DoubleBookingError(ReservationError):
    """Raised when an overlapping reservation exists for the requested table."""
    def __init__(self, message: str, conflicting_reservation: dict = None):
        super().__init__(message)
        self.conflicting_reservation = conflicting_reservation


class ValidationError(ReservationError):
    """Raised when request payload fails validation checks."""
    pass


class ReservationService:
    """Service layer managing MongoDB CRUD, Overlap Checks, and Aggregation."""

    @staticmethod
    def parse_datetime(dt_input: Any) -> datetime:
        """
        Normalize input into a UTC or timezone-aware BSON Date (datetime).
        Accepts ISO strings, date/time strings, or datetime instances.
        """
        if isinstance(dt_input, datetime):
            # If naive, treat as UTC
            if dt_input.tzinfo is None:
                return dt_input.replace(tzinfo=timezone.utc)
            return dt_input.astimezone(timezone.utc)

        if isinstance(dt_input, str):
            # Try parsing ISO format
            clean_str = dt_input.strip()
            # Replace trailing Z if present
            if clean_str.endswith("Z"):
                clean_str = clean_str[:-1] + "+00:00"
            # Handle query string unescaping where '+' in timezone offset was decoded to space:
            # e.g., '2026-11-28T18:00:00 00:00' -> '2026-11-28T18:00:00+00:00'
            if " " in clean_str:
                parts = clean_str.rsplit(" ", 1)
                if len(parts) == 2 and ":" in parts[1] and ("T" in parts[0] or "-" in parts[0]):
                    clean_str = f"{parts[0]}+{parts[1]}"
            try:
                dt = datetime.fromisoformat(clean_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except ValueError:
                # Try common formats
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                    try:
                        dt = datetime.strptime(clean_str, fmt)
                        return dt.replace(tzinfo=timezone.utc)
                    except ValueError:
                        continue
                raise ValidationError(f"Invalid date/time format: '{dt_input}'. Expected ISO 8601 (YYYY-MM-DDTHH:MM).")
        raise ValidationError(f"Invalid datetime input type: {type(dt_input).__name__}")

    @classmethod
    def check_table_overlap(
        cls,
        table_number: int,
        start_time: datetime,
        duration_minutes: int,
        exclude_id: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Check if any active (non-cancelled) reservation overlaps with [start_time, start_time + duration].
        Two intervals [A_start, A_end] and [B_start, B_end] overlap iff:
            A_start < B_end AND A_end > B_start

        Uses MongoDB's $expr and compound index on (table_number, reservation_time).
        Returns the conflicting reservation document if found, else None.
        """
        end_time = start_time + timedelta(minutes=duration_minutes)
        collection = get_reservations_collection()

        overlap_query = {
            "table_number": int(table_number),
            "status": {"$nin": ["cancelled"]},  # Cancelled bookings do not block tables
            "$expr": {
                "$and": [
                    # existing start_time < requested end_time
                    {"$lt": ["$reservation_time", end_time]},
                    # existing end_time (start_time + duration) > requested start_time
                    {
                        "$gt": [
                            {
                                "$add": [
                                    "$reservation_time",
                                    {"$multiply": ["$duration_minutes", 60 * 1000]},
                                ]
                            },
                            start_time,
                        ]
                    },
                ]
            },
        }

        if exclude_id:
            try:
                overlap_query["_id"] = {"$ne": ObjectId(exclude_id)}
            except Exception:
                pass

        conflict = collection.find_one(overlap_query)
        return conflict

    @classmethod
    def create_reservation(cls, data: Dict[str, Any]) -> dict:
        """
        Insert a new reservation document into MongoDB using insert_one().
        Enforces validation and double-booking interval checks.
        """
        # 1. Validate required fields
        required_fields = ["customer_name", "customer_email", "customer_phone", "table_number", "guests", "reservation_time"]
        for field in required_fields:
            if field not in data or data[field] is None or data[field] == "":
                raise ValidationError(f"Field '{field}' is required.")

        # 2. Type conversions and business rules
        try:
            table_number = int(data["table_number"])
            if table_number < 1:
                raise ValueError()
        except (ValueError, TypeError):
            raise ValidationError("table_number must be a positive integer.")

        try:
            guests = int(data["guests"])
            if guests < 1 or guests > 30:
                raise ValueError()
        except (ValueError, TypeError):
            raise ValidationError("guests must be a positive integer between 1 and 30.")

        duration_minutes = int(data.get("duration_minutes", Config.DEFAULT_RESERVATION_DURATION_MINUTES))
        if duration_minutes < 15 or duration_minutes > 360:
            raise ValidationError("duration_minutes must be between 15 and 360.")

        start_time = cls.parse_datetime(data["reservation_time"])
        now_utc = datetime.now(timezone.utc)

        status = data.get("status", "confirmed").lower()
        if status not in Config.ALLOWED_STATUSES:
            raise ValidationError(f"Invalid status '{status}'. Allowed: {Config.ALLOWED_STATUSES}")

        # 3. Double-Booking Prevention Check
        conflict = cls.check_table_overlap(table_number, start_time, duration_minutes)
        if conflict:
            conflict_start = conflict["reservation_time"].strftime("%Y-%m-%d %H:%M")
            conflict_duration = conflict.get("duration_minutes", 90)
            msg = (
                f"Double-booking conflict: Table {table_number} is already booked from "
                f"{conflict_start} UTC for {conflict_duration} minutes "
                f"(Reservation ID: {conflict['_id']})."
            )
            raise DoubleBookingError(msg, serialize_document(conflict))

        # 4. Construct BSON document
        reservation_doc = {
            "customer_name": str(data["customer_name"]).strip(),
            "customer_email": str(data["customer_email"]).strip().lower(),
            "customer_phone": str(data["customer_phone"]).strip(),
            "table_number": table_number,
            "guests": guests,
            "reservation_time": start_time,
            "duration_minutes": duration_minutes,
            "special_requests": str(data.get("special_requests", "")).strip(),
            "status": status,
            "created_at": now_utc,
            "updated_at": now_utc,
        }

        # 5. Insert into MongoDB
        collection = get_reservations_collection()
        try:
            result = collection.insert_one(reservation_doc)
            reservation_doc["_id"] = result.inserted_id
            return serialize_document(reservation_doc)
        except WriteError as write_err:
            raise ValidationError(f"MongoDB Schema Validation Failure: {write_err.details}")

    @classmethod
    def get_reservation_by_id(cls, reservation_id: str) -> Optional[dict]:
        """Retrieve single reservation by ObjectId using find_one()."""
        try:
            obj_id = ObjectId(reservation_id)
        except Exception:
            raise ValidationError("Invalid reservation ID format.")

        collection = get_reservations_collection()
        doc = collection.find_one({"_id": obj_id})
        return serialize_document(doc)

    @classmethod
    def list_reservations(
        cls,
        status: Optional[str] = None,
        table_number: Optional[int] = None,
        start_date: Optional[Any] = None,
        end_date: Optional[Any] = None,
        search_query: Optional[str] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> List[dict]:
        """
        Query reservations using MongoDB find() with filtering, date ranges, and sorting.
        Implements date range filtering using $gte and $lt.
        """
        collection = get_reservations_collection()
        query: Dict[str, Any] = {}

        if status and status.lower() != "all":
            query["status"] = status.lower()

        if table_number:
            query["table_number"] = int(table_number)

        # Date range queries using $gte and $lt
        date_conditions = {}
        if start_date:
            date_conditions["$gte"] = cls.parse_datetime(start_date)
        if end_date:
            date_conditions["$lt"] = cls.parse_datetime(end_date)
        if date_conditions:
            query["reservation_time"] = date_conditions

        # Search query matching customer name, email, or phone
        if search_query:
            clean_search = search_query.strip()
            query["$or"] = [
                {"customer_name": {"$regex": clean_search, "$options": "i"}},
                {"customer_email": {"$regex": clean_search, "$options": "i"}},
                {"customer_phone": {"$regex": clean_search, "$options": "i"}},
            ]

        cursor = (
            collection.find(query)
            .sort("reservation_time", ASCENDING)
            .skip(skip)
            .limit(limit)
        )
        return serialize_documents(cursor)

    @classmethod
    def update_reservation(cls, reservation_id: str, update_data: Dict[str, Any]) -> dict:
        """
        Update an existing reservation using update_one().
        Re-evaluates double-booking overlap if table or time is modified.
        """
        try:
            obj_id = ObjectId(reservation_id)
        except Exception:
            raise ValidationError("Invalid reservation ID format.")

        collection = get_reservations_collection()
        existing = collection.find_one({"_id": obj_id})
        if not existing:
            raise ReservationError("Reservation not found.")

        # Determine target values
        new_table = int(update_data.get("table_number", existing["table_number"]))
        new_duration = int(update_data.get("duration_minutes", existing.get("duration_minutes", 90)))
        
        if "reservation_time" in update_data:
            new_time = cls.parse_datetime(update_data["reservation_time"])
        else:
            new_time = existing["reservation_time"]

        new_status = update_data.get("status", existing["status"]).lower()
        if new_status not in Config.ALLOWED_STATUSES:
            raise ValidationError(f"Invalid status '{new_status}'. Allowed: {Config.ALLOWED_STATUSES}")

        # Check overlap only if table, time, duration, or active status changed
        if new_status != "cancelled":
            conflict = cls.check_table_overlap(
                table_number=new_table,
                start_time=new_time,
                duration_minutes=new_duration,
                exclude_id=str(obj_id),
            )
            if conflict:
                conflict_start = conflict["reservation_time"].strftime("%Y-%m-%d %H:%M")
                msg = (
                    f"Double-booking conflict: Table {new_table} is already booked from "
                    f"{conflict_start} UTC (Reservation ID: {conflict['_id']})."
                )
                raise DoubleBookingError(msg, serialize_document(conflict))

        # Build update fields
        now_utc = datetime.now(timezone.utc)
        set_fields: Dict[str, Any] = {
            "updated_at": now_utc,
            "status": new_status,
            "table_number": new_table,
            "duration_minutes": new_duration,
            "reservation_time": new_time,
        }

        if "customer_name" in update_data:
            set_fields["customer_name"] = str(update_data["customer_name"]).strip()
        if "customer_email" in update_data:
            set_fields["customer_email"] = str(update_data["customer_email"]).strip().lower()
        if "customer_phone" in update_data:
            set_fields["customer_phone"] = str(update_data["customer_phone"]).strip()
        if "guests" in update_data:
            set_fields["guests"] = int(update_data["guests"])
        if "special_requests" in update_data:
            set_fields["special_requests"] = str(update_data["special_requests"]).strip()

        try:
            collection.update_one({"_id": obj_id}, {"$set": set_fields})
            updated_doc = collection.find_one({"_id": obj_id})
            return serialize_document(updated_doc)
        except WriteError as write_err:
            raise ValidationError(f"MongoDB Schema Validation Failure: {write_err.details}")

    @classmethod
    def cancel_reservation(cls, reservation_id: str, reason: str = "") -> dict:
        """
        Soft-delete operation: Updates status to 'cancelled'.
        Preserves customer history and audit trail while freeing the table immediately.
        """
        try:
            obj_id = ObjectId(reservation_id)
        except Exception:
            raise ValidationError("Invalid reservation ID format.")

        collection = get_reservations_collection()
        existing = collection.find_one({"_id": obj_id})
        if not existing:
            raise ReservationError("Reservation not found.")

        now_utc = datetime.now(timezone.utc)
        special_requests = existing.get("special_requests", "")
        if reason:
            special_requests = f"{special_requests} [Cancelled reason: {reason}]".strip()

        collection.update_one(
            {"_id": obj_id},
            {
                "$set": {
                    "status": "cancelled",
                    "special_requests": special_requests,
                    "updated_at": now_utc,
                }
            },
        )
        updated_doc = collection.find_one({"_id": obj_id})
        return serialize_document(updated_doc)

    @classmethod
    def delete_reservation(cls, reservation_id: str) -> bool:
        """
        Hard-delete operation: Permanently removes document from collection using delete_one().
        """
        try:
            obj_id = ObjectId(reservation_id)
        except Exception:
            raise ValidationError("Invalid reservation ID format.")

        collection = get_reservations_collection()
        result = collection.delete_one({"_id": obj_id})
        if result.deleted_count == 0:
            raise ReservationError("Reservation not found or already deleted.")
        return True

    # ==========================================================================
    # MongoDB Aggregation Pipelines ($group and $sort)
    # ==========================================================================

    @classmethod
    def get_summary_by_status(cls) -> List[dict]:
        """
        Aggregation Pipeline: Summarize bookings by status.
        Uses $group and $sort to calculate total booking counts and guest counts per status.
        """
        collection = get_reservations_collection()
        pipeline = [
            {
                "$group": {
                    "_id": "$status",
                    "booking_count": {"$sum": 1},
                    "total_guests": {"$sum": "$guests"},
                }
            },
            {"$sort": {"booking_count": DESCENDING}},
            {
                "$project": {
                    "_id": 0,
                    "status": "$_id",
                    "booking_count": 1,
                    "total_guests": 1,
                }
            },
        ]
        return list(collection.aggregate(pipeline))

    @classmethod
    def get_summary_by_table(cls) -> List[dict]:
        """
        Aggregation Pipeline: Summarize bookings by table.
        Uses $group and $sort to compute bookings, total guests, and active bookings per table.
        """
        collection = get_reservations_collection()
        pipeline = [
            {
                "$group": {
                    "_id": "$table_number",
                    "booking_count": {"$sum": 1},
                    "total_guests": {"$sum": "$guests"},
                    "confirmed_count": {
                        "$sum": {"$cond": [{"$eq": ["$status", "confirmed"]}, 1, 0]}
                    },
                    "seated_count": {
                        "$sum": {"$cond": [{"$eq": ["$status", "seated"]}, 1, 0]}
                    },
                    "completed_count": {
                        "$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}
                    },
                    "cancelled_count": {
                        "$sum": {"$cond": [{"$eq": ["$status", "cancelled"]}, 1, 0]}
                    },
                }
            },
            {"$sort": {"_id": ASCENDING}},
            {
                "$project": {
                    "_id": 0,
                    "table_number": "$_id",
                    "booking_count": 1,
                    "total_guests": 1,
                    "confirmed_count": 1,
                    "seated_count": 1,
                    "completed_count": 1,
                    "cancelled_count": 1,
                }
            },
        ]
        return list(collection.aggregate(pipeline))

    @classmethod
    def get_overall_metrics(cls) -> dict:
        """
        Aggregation Pipeline: Compute high-level dashboard metrics across all reservations.
        """
        collection = get_reservations_collection()
        now_utc = datetime.now(timezone.utc)
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_bookings": {"$sum": 1},
                    "total_guests": {"$sum": "$guests"},
                    "confirmed_bookings": {
                        "$sum": {"$cond": [{"$eq": ["$status", "confirmed"]}, 1, 0]}
                    },
                    "seated_bookings": {
                        "$sum": {"$cond": [{"$eq": ["$status", "seated"]}, 1, 0]}
                    },
                    "completed_bookings": {
                        "$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}
                    },
                    "cancelled_bookings": {
                        "$sum": {"$cond": [{"$eq": ["$status", "cancelled"]}, 1, 0]}
                    },
                    "upcoming_bookings": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$and": [
                                        {"$gte": ["$reservation_time", now_utc]},
                                        {"$in": ["$status", ["confirmed", "pending"]]},
                                    ]
                                },
                                1,
                                0,
                            ]
                        }
                    },
                }
            },
            {"$project": {"_id": 0}},
        ]
        results = list(collection.aggregate(pipeline))
        if results:
            return results[0]
        return {
            "total_bookings": 0,
            "total_guests": 0,
            "confirmed_bookings": 0,
            "seated_bookings": 0,
            "completed_bookings": 0,
            "cancelled_bookings": 0,
            "upcoming_bookings": 0,
        }
