"""
Restaurant Table Reservation System - Main Flask Application.
Provides RESTful API endpoints and web interface for reservation management,
double-booking validation, and MongoDB aggregation analytics.
"""

import os
import logging
from datetime import datetime, timezone
from flask import Flask, render_template, request, jsonify, abort

from config import Config
from database import check_connection, get_reservations_collection
from services.reservation_service import (
    ReservationService,
    DoubleBookingError,
    ValidationError,
    ReservationError,
)
from scripts.init_db import initialize_database
from scripts.seed_data import seed_sample_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("app")

app = Flask(__name__)
app.config.from_object(Config)


# ==============================================================================
# HTML Page Route
# ==============================================================================
@app.route("/")
def index():
    """Render the primary single-page restaurant reservation application."""
    return render_template("index.html")


# ==============================================================================
# REST API: System & Health Endpoints
# ==============================================================================
@app.route("/api/health", methods=["GET"])
def health_check():
    """
    Check MongoDB database connection status, server version,
    and inspect collection indexes.
    """
    status = check_connection()
    if status["connected"]:
        collection = get_reservations_collection()
        indexes = collection.index_information()
        doc_count = collection.count_documents({})
        status["indexes"] = indexes
        status["document_count"] = doc_count
        return jsonify(status), 200
    return jsonify(status), 503


@app.route("/api/seed", methods=["POST"])
def seed_database():
    """Seed sample reservations idempotently."""
    try:
        result = seed_sample_data()
        return jsonify({
            "success": True,
            "message": "Sample data seeded successfully without duplicates.",
            "details": result,
        }), 200
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# ==============================================================================
# REST API: Reservations CRUD & Overlap Checking
# ==============================================================================
@app.route("/api/reservations", methods=["GET"])
def list_reservations():
    """
    List reservations with optional filters:
    - status: 'confirmed', 'seated', 'completed', 'cancelled', 'pending', or 'all'
    - table_number: integer
    - start_date / end_date: ISO 8601 string for date-range queries ($gte, $lt)
    - search: customer name, email, or phone search substring
    """
    try:
        status = request.args.get("status")
        table_number = request.args.get("table_number")
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        search = request.args.get("search")
        limit = int(request.args.get("limit", 100))
        skip = int(request.args.get("skip", 0))

        reservations = ReservationService.list_reservations(
            status=status,
            table_number=table_number,
            start_date=start_date,
            end_date=end_date,
            search_query=search,
            limit=limit,
            skip=skip,
        )
        return jsonify({"success": True, "count": len(reservations), "data": reservations}), 200
    except Exception as exc:
        logger.error("Error listing reservations: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 400


@app.route("/api/reservations/<reservation_id>", methods=["GET"])
def get_reservation(reservation_id):
    """Retrieve a single reservation document by its ObjectId."""
    try:
        reservation = ReservationService.get_reservation_by_id(reservation_id)
        if not reservation:
            return jsonify({"success": False, "error": "Reservation not found"}), 404
        return jsonify({"success": True, "data": reservation}), 200
    except ValidationError as err:
        return jsonify({"success": False, "error": str(err)}), 400
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/reservations/check-availability", methods=["GET"])
def check_availability():
    """
    Check if a table is available for a specified date, time, and duration
    without creating a reservation.
    """
    try:
        table_number = request.args.get("table_number")
        reservation_time = request.args.get("reservation_time")
        duration = int(request.args.get("duration_minutes", Config.DEFAULT_RESERVATION_DURATION_MINUTES))
        exclude_id = request.args.get("exclude_id")

        if not table_number or not reservation_time:
            return jsonify({"success": False, "error": "table_number and reservation_time are required."}), 400

        dt = ReservationService.parse_datetime(reservation_time)
        conflict = ReservationService.check_table_overlap(
            table_number=int(table_number),
            start_time=dt,
            duration_minutes=duration,
            exclude_id=exclude_id,
        )

        if conflict:
            return jsonify({
                "available": False,
                "message": f"Table {table_number} is already booked at that time.",
                "conflicting_reservation_id": str(conflict["_id"]),
            }), 200

        return jsonify({
            "available": True,
            "message": f"Table {table_number} is available for booking.",
        }), 200
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@app.route("/api/reservations", methods=["POST"])
def create_reservation():
    """
    Create a new reservation.
    Executes insert_one() with schema validation and double-booking interval checks.
    """
    payload = request.get_json()
    if not payload:
        return jsonify({"success": False, "error": "JSON request body required"}), 400

    try:
        created = ReservationService.create_reservation(payload)
        return jsonify({
            "success": True,
            "message": "Reservation confirmed and saved to MongoDB.",
            "data": created,
        }), 201
    except DoubleBookingError as dbe:
        return jsonify({
            "success": False,
            "error_type": "DOUBLE_BOOKING",
            "message": str(dbe),
            "conflict": dbe.conflicting_reservation,
        }), 409
    except ValidationError as ve:
        return jsonify({"success": False, "error_type": "VALIDATION_ERROR", "message": str(ve)}), 400
    except Exception as exc:
        logger.error("Failed to create reservation: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/reservations/<reservation_id>", methods=["PUT"])
def update_reservation(reservation_id):
    """
    Update an existing reservation document using update_one().
    Re-checks double-booking interval if table or time changed.
    """
    payload = request.get_json()
    if not payload:
        return jsonify({"success": False, "error": "JSON request body required"}), 400

    try:
        updated = ReservationService.update_reservation(reservation_id, payload)
        return jsonify({
            "success": True,
            "message": "Reservation updated successfully in MongoDB.",
            "data": updated,
        }), 200
    except DoubleBookingError as dbe:
        return jsonify({
            "success": False,
            "error_type": "DOUBLE_BOOKING",
            "message": str(dbe),
            "conflict": dbe.conflicting_reservation,
        }), 409
    except (ValidationError, ReservationError) as err:
        return jsonify({"success": False, "message": str(err)}), 400
    except Exception as exc:
        logger.error("Failed to update reservation: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/reservations/<reservation_id>/cancel", methods=["PATCH", "POST"])
def cancel_reservation(reservation_id):
    """
    Soft-delete cancellation: Updates reservation status to 'cancelled'.
    Frees the table for other guests while preserving the record for auditing.
    """
    payload = request.get_json(silent=True) or {}
    reason = payload.get("reason", "")
    try:
        cancelled = ReservationService.cancel_reservation(reservation_id, reason=reason)
        return jsonify({
            "success": True,
            "message": "Reservation cancelled successfully. Table is now available.",
            "data": cancelled,
        }), 200
    except ReservationError as err:
        return jsonify({"success": False, "message": str(err)}), 400
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/reservations/<reservation_id>", methods=["DELETE"])
def delete_reservation(reservation_id):
    """
    Hard-delete operation: Permanently removes the document using delete_one().
    """
    try:
        ReservationService.delete_reservation(reservation_id)
        return jsonify({
            "success": True,
            "message": f"Reservation {reservation_id} permanently deleted from MongoDB.",
        }), 200
    except ReservationError as err:
        return jsonify({"success": False, "message": str(err)}), 400
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# ==============================================================================
# REST API: MongoDB Aggregation Analytics
# ==============================================================================
@app.route("/api/analytics/summary", methods=["GET"])
def analytics_summary():
    """
    Returns aggregated metrics computed using MongoDB $group and $sort pipelines:
    1. Overall high-level metrics (total bookings, guests, upcoming, completed)
    2. Grouped by status (counts & guests)
    3. Grouped by table (counts, guests, status breakdown)
    """
    try:
        overall = ReservationService.get_overall_metrics()
        by_status = ReservationService.get_summary_by_status()
        by_table = ReservationService.get_summary_by_table()
        return jsonify({
            "success": True,
            "overall": overall,
            "by_status": by_status,
            "by_table": by_table,
        }), 200
    except Exception as exc:
        logger.error("Error executing aggregation pipelines: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


# ==============================================================================
# Application Startup
# ==============================================================================
if __name__ == "__main__":
    # Ensure database validation and indexes exist before serving requests
    logger.info("Initializing database schema validation and indexes...")
    initialize_database()
    logger.info("Starting Flask server on port %d...", Config.PORT)
    app.run(host="0.0.0.0", port=Config.PORT, debug=Config.DEBUG)

