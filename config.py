"""
Application Configuration Module
Reads configuration from environment variables (.env file).
"""

import os
from dotenv import load_dotenv

# Load .env file from project root
load_dotenv()


class Config:
    """Application configuration values."""
    SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret-key-for-development-only")
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    DEBUG = os.getenv("FLASK_DEBUG", "1").lower() in ("1", "true", "yes")
    PORT = int(os.getenv("PORT", "5000"))

    # MongoDB Configuration
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/restaurant_db")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "restaurant_db")

    # Business Rules
    DEFAULT_RESERVATION_DURATION_MINUTES = 90
    MIN_GUESTS = 1
    MAX_GUESTS = 20
    MIN_TABLE_NUMBER = 1
    MAX_TABLE_NUMBER = 20
    ALLOWED_STATUSES = ["pending", "confirmed", "seated", "completed", "cancelled"]

