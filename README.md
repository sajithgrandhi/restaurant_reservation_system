# Restaurant Table Reservation System (MongoDB Integration)

A production-grade, full-stack Restaurant Table Reservation System built with **Python Flask**, **PyMongo**, and **MongoDB**. This project provides complete MongoDB integration featuring JSON Schema validation, compound indexing, double-booking interval collision prevention, BSON Date range queries, and real-time MongoDB aggregation pipelines (`$group` and `$sort`).

---

## Table of Contents
1. [Architecture & System Overview](#1-architecture--system-overview)
2. [Project File Structure](#2-project-file-structure)
3. [MongoDB Setup: Local Community Server vs Atlas Cloud](#3-mongodb-setup-local-community-server-vs-atlas-cloud)
4. [Step-by-Step Windows & VS Code Setup](#4-step-by-step-windows--vs-code-setup)
5. [Database Initialization & Schema Validation](#5-database-initialization--schema-validation)
6. [CRUD Operations & Business Logic](#6-crud-operations--business-logic)
7. [Double-Booking Prevention & Concurrency Handling](#7-double-booking-prevention--concurrency-handling)
8. [Date Queries & BSON Datetime Handling](#8-date-queries--bson-datetime-handling)
9. [MongoDB Aggregation Pipelines ($group & $sort)](#9-mongodb-aggregation-pipelines-group--sort)
10. [Indexes & Inspection Strategy](#10-indexes--inspection-strategy)
11. [Sample Data Generation](#11-sample-data-generation)
12. [Testing Suite & Verification](#12-testing-suite--verification)
13. [Database Inspection (mongosh & Compass)](#13-database-inspection-mongosh--compass)
14. [Security & Credentials Management](#14-security--credentials-management)

---

## 1. Architecture & System Overview

```
                      +---------------------------------------+
                      |           Web Browser (UI)            |
                      |  - Interactive Reservation Form       |
                      |  - Live Table Availability Checker    |
                      |  - Filterable Reservation Roster      |
                      |  - Real-Time Aggregation Dashboard    |
                      +-------------------+-------------------+
                                          |
                                HTTP / REST JSON
                                          |
                                          v
                      +---------------------------------------+
                      |         Flask Backend (app.py)        |
                      |  - RESTful API Endpoints              |
                      |  - Request Normalization & Validation |
                      +-------------------+-------------------+
                                          |
                                Python Function Calls
                                          |
                                          v
                      +---------------------------------------+
                      |  Reservation Service (Business Logic) |
                      |  - Overlapping Interval Check ($expr) |
                      |  - BSON Datetime Normalization        |
                      |  - Aggregation Pipelines Builder      |
                      +-------------------+-------------------+
                                          |
                                 PyMongo Connection
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                        MongoDB Server (restaurant_db)                             |
|                                                                                   |
|  Collection: reservations                                                         |
|  ├── Strict JSON Schema Validation ($jsonSchema)                                  |
|  │   ├── Required: name, email, phone, table_number, guests, reservation_time     |
|  │   ├── Type constraints: string, int/long, date (BSON Date)                     |
|  │   └── Range constraints: guests >= 1, table_number >= 1, status enum          |
|  └── Active Indexes:                                                              |
|      ├── idx_table_time:       (table_number: 1, reservation_time: 1) [Compound]  |
|      ├── idx_reservation_time: (reservation_time: 1)                              |
|      ├── idx_customer_email:   (customer_email: 1)                                |
|      └── idx_status:           (status: 1)                                        |
+-----------------------------------------------------------------------------------+
```

---

## 2. Project File Structure

```
restaurant_reservation_system/
│
├── app.py                      # Flask web application & REST API routes
├── config.py                   # App configuration & environment parsing
├── database.py                 # PyMongo connection pool, BSON schema & serializers
│
├── services/
│   └── reservation_service.py  # Business logic: CRUD, overlap check, aggregations
│
├── static/
│   ├── css/
│   │   └── style.css           # Modern dining UI stylesheet
│   └── js/
│       └── app.js              # Client controller, API client & dashboard charts
│
├── templates/
│   └── index.html              # Primary responsive web application interface
│
├── scripts/
│   ├── init_db.py              # Safe, idempotent database schema & index initializer
│   └── seed_data.py            # Fictional reservation seeder (duplicate-safe)
│
├── tests/
│   ├── test_reservation_system.py # Domain & database integration test suite
│   └── test_api_endpoints.py      # Flask REST API integration test suite
│
├── .env.example                # Template for environment variables
├── .env                        # Local development environment configuration
├── .gitignore                  # Git exclusion rules
├── requirements.txt            # Python dependencies (Flask, PyMongo, python-dotenv)
└── README.md                   # Complete documentation & operational manual
```

---

## 3. MongoDB Setup: Local Community Server vs Atlas Cloud

### Option A: MongoDB Community Server (Local Windows Installation)

1. **Download & Install:**
   - Download the **MongoDB Community Server .msi installer** from [mongodb.com/try/download/community](https://www.mongodb.com/try/download/community).
   - In the installer wizard, select **"Complete"** installation.
   - Ensure the checkbox **"Install MongoDB as a Service"** is checked. This installs the MongoDB Windows Service (`MongoDB`) and starts it automatically on system startup.
   - Install **MongoDB Compass** (graphical client) during the wizard.

2. **Verify Local Service in Windows:**
   - Open PowerShell as Administrator or Windows Services (`services.msc`).
   - Run:
     ```powershell
     Get-Service -Name MongoDB
     ```
     Status should report `Running`.

3. **Connection String:**
   ```env
   MONGO_URI=mongodb://localhost:27017/restaurant_db
   MONGO_DB_NAME=restaurant_db
   ```

---

### Option B: MongoDB Atlas (Cloud Database)

1. **Create Free Cloud Cluster:**
   - Sign up or log in at [cloud.mongodb.com](https://cloud.mongodb.com).
   - Create a free M0 tier cluster (e.g., hosted on AWS / Google Cloud).

2. **Configure Database Access:**
   - Navigate to **Security > Database Access**.
   - Click **Add New Database User**.
   - Choose **Password** authentication:
     - Username: `restaurant_admin`
     - Password: `YourSecurePassword123!`
   - Assign built-in role: `Read and write to any database`.

3. **Configure Network Access (IP Whitelist):**
   - Navigate to **Security > Network Access**.
   - Click **Add IP Address**.
   - Choose **Add Current IP Address** (or `0.0.0.0/0` for universal development access).

4. **Retrieve Connection String:**
   - Click **Database > Connect > Drivers > Python**.
   - Copy the SRV URI and update `.env`:
     ```env
     MONGO_URI=mongodb+srv://restaurant_admin:YourSecurePassword123!@cluster0.abcde.mongodb.net/restaurant_db?retryWrites=true&w=majority
     MONGO_DB_NAME=restaurant_db
     ```

---

## 4. Step-by-Step Windows & VS Code Setup

### Prerequisites
- **Python 3.10+** installed on Windows with `Add python.exe to PATH` checked.
- **VS Code** with Python extension installed.

### Step 1: Open Project in VS Code
Open VS Code and navigate to the project directory:
```powershell
cd c:\Users\Sajit\OneDrive\Documents\antigravity
code .
```

### Step 2: Create and Activate a Virtual Environment
In the VS Code integrated terminal (`Ctrl + \``):
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
*(If PowerShell displays an execution policy error, run: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`)*

### Step 3: Install Required Dependencies
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables
Copy the example configuration to `.env`:
```powershell
copy .env.example .env
```
Ensure `MONGO_URI` matches your local MongoDB server (`mongodb://localhost:27017/restaurant_db`) or Atlas connection string.

### Step 5: Initialize the Database (Schema & Indexes)
Execute the safe initialization script:
```powershell
python scripts/init_db.py
```

### Step 6: Seed Demo Reservations (Optional)
Populate sample test bookings across diverse dates, tables, and statuses:
```powershell
python scripts/seed_data.py
```

### Step 7: Run the Test Suites
Run all automated test suites to ensure 100% database and API integrity:
```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

### Step 8: Start the Web Application
```powershell
python app.py
```
Open your browser and navigate to:
```
http://localhost:5000
```

---

## 5. Database Initialization & Schema Validation

The initialization script (`scripts/init_db.py`) is designed to be **safe and idempotent**:
- If collection `reservations` does not exist: it creates it using `db.create_collection(...)` attaching the JSON Schema validator with `validationAction="error"` and `validationLevel="strict"`.
- If collection already exists: it updates the validator in-place using MongoDB's `collMod` command without dropping or modifying existing documents.

### MongoDB JSON Schema Validator Specification
```json
{
  "$jsonSchema": {
    "bsonType": "object",
    "required": [
      "customer_name",
      "customer_email",
      "customer_phone",
      "table_number",
      "guests",
      "reservation_time",
      "status"
    ],
    "properties": {
      "_id": { "bsonType": "objectId" },
      "customer_name": { "bsonType": "string", "minLength": 2, "maxLength": 100 },
      "customer_email": {
        "bsonType": "string",
        "pattern": "^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+$"
      },
      "customer_phone": { "bsonType": "string", "minLength": 7, "maxLength": 25 },
      "table_number": { "bsonType": ["int", "long"], "minimum": 1, "maximum": 50 },
      "guests": { "bsonType": ["int", "long"], "minimum": 1, "maximum": 30 },
      "reservation_time": { "bsonType": "date" },
      "duration_minutes": { "bsonType": ["int", "long"], "minimum": 15, "maximum": 360 },
      "special_requests": { "bsonType": "string", "maxLength": 500 },
      "status": { "enum": ["pending", "confirmed", "seated", "completed", "cancelled"] },
      "created_at": { "bsonType": "date" },
      "updated_at": { "bsonType": "date" }
    },
    "additionalProperties": false
  }
}
```

---

## 6. CRUD Operations & Business Logic

All data operations are implemented through `services/reservation_service.py` using official PyMongo driver methods:

| Operation | PyMongo Method | Implementation & Purpose |
| :--- | :--- | :--- |
| **Create** | `insert_one()` | Inserts a validated document after running interval collision checks. |
| **Read (List)** | `find()` | Queries documents with date range filters (`$gte`, `$lt`), status filtering, and customer text search. |
| **Read (Single)** | `find_one()` | Fetches a single reservation by its unique BSON `ObjectId`. |
| **Update** | `update_one()` | Updates party size, duration, table, or notes with timestamp update. |
| **Soft Delete** | `update_one()` | Sets `status: "cancelled"`. Frees table while preserving audit history. |
| **Hard Delete** | `delete_one()` | Permanently purges document from MongoDB collection. |

### Soft Delete vs Hard Delete
- **Soft Delete (`status="cancelled"`):** Recommended for restaurant systems. It preserves guest history, no-show metrics, and audit logs. The double-booking query excludes records where `status == "cancelled"`, making the table available immediately upon cancellation.
- **Hard Delete (`delete_one`):** Used when data must be permanently erased (e.g., GDPR data erasure requests or cleaning up test fixtures).

---

## 7. Double-Booking Prevention & Concurrency Handling

### Overlapping Interval Logic
Two intervals $[S_A, E_A]$ and $[S_B, E_B]$ overlap if and only if:
$$\text{Start}_A < \text{End}_B \quad \text{and} \quad \text{End}_A > \text{Start}_B$$

When reserving Table $T$ for $[\text{Start}_{\text{new}}, \text{End}_{\text{new}}]$, the system executes a MongoDB query:
```python
overlap_query = {
    "table_number": table_number,
    "status": {"$nin": ["cancelled"]},
    "$expr": {
        "$and": [
            {"$lt": ["$reservation_time", new_end_time]},
            {
                "$gt": [
                    {
                        "$add": [
                            "$reservation_time",
                            {"$multiply": ["$duration_minutes", 60 * 1000]}
                        ]
                    },
                    new_start_time
                ]
            }
        ]
    }
}
```

### Concurrency Limitations & Solutions
1. **Application-Level Check (Current Implementation):**
   - Fast and leverages the compound index on `(table_number, reservation_time)`.
   - **Limitation:** In ultra-high concurrency (e.g. dozens of simultaneous requests in the same millisecond), a Time-of-Check to Time-of-Use (TOCTOU) race condition can exist between `check_table_overlap()` and `insert_one()`.
2. **Production High-Concurrency Strategies:**
   - **MongoDB Multi-Document Transactions:** On replica sets and Atlas clusters, execute the check and insert inside `client.start_session()` with a transaction.
   - **Slot Bucket Unique Index:** Discretize dining times into fixed 30-minute slot documents and enforce a unique compound index: `{ table_number: 1, slot_time: 1 }`. Any concurrent insert attempting the same slot immediately throws a duplicate key error (`E11000`), guaranteeing zero double-bookings at the storage layer.

---

## 8. Date Queries & BSON Datetime Handling

MongoDB represents dates internally as 64-bit integers representing milliseconds since the Unix epoch (BSON type 9: `Date`).

### Implementation Rules:
1. Dates are never stored as arbitrary strings.
2. The service converts all incoming ISO 8601 strings to timezone-aware Python `datetime.datetime` objects with UTC timezone before querying or saving.
3. Date range queries are executed using `$gte` (greater than or equal) and `$lt` (less than):

```python
# Query reservations for a specific calendar day:
start_of_day = datetime(2026, 10, 28, 0, 0, 0, tzinfo=timezone.utc)
end_of_day = datetime(2026, 10, 29, 0, 0, 0, tzinfo=timezone.utc)

cursor = collection.find({
    "reservation_time": {
        "$gte": start_of_day,
        "$lt": end_of_day
    }
}).sort("reservation_time", 1)
```

---

## 9. MongoDB Aggregation Pipelines ($group & $sort)

The system leverages MongoDB's native aggregation pipeline for real-time analytics without computing metrics in application memory.

### Pipeline 1: Status Distribution Summary
Groups reservations by status, computing booking count and total guest volume, sorted descending by count:
```javascript
db.reservations.aggregate([
  {
    $group: {
      _id: "$status",
      booking_count: { $sum: 1 },
      total_guests: { $sum: "$guests" }
    }
  },
  { $sort: { booking_count: -1 } },
  {
    $project: {
      _id: 0,
      status: "$_id",
      booking_count: 1,
      total_guests: 1
    }
  }
])
```

### Pipeline 2: Table Utilization Breakdown
Summarizes dining activity by table number, sorted ascending by table:
```javascript
db.reservations.aggregate([
  {
    $group: {
      _id: "$table_number",
      booking_count: { $sum: 1 },
      total_guests: { $sum: "$guests" },
      confirmed_count: {
        $sum: { $cond: [{ $eq: ["$status", "confirmed"] }, 1, 0] }
      },
      seated_count: {
        $sum: { $cond: [{ $eq: ["$status", "seated"] }, 1, 0] }
      },
      completed_count: {
        $sum: { $cond: [{ $eq: ["$status", "completed"] }, 1, 0] }
      },
      cancelled_count: {
        $sum: { $cond: [{ $eq: ["$status", "cancelled"] }, 1, 0] }
      }
    }
  },
  { $sort: { _id: 1 } },
  {
    $project: {
      _id: 0,
      table_number: "$_id",
      booking_count: 1,
      total_guests: 1,
      confirmed_count: 1,
      seated_count: 1,
      completed_count: 1,
      cancelled_count: 1
    }
  }
])
```

---

## 10. Indexes & Inspection Strategy

The application maintains 4 custom indexes configured via `scripts/init_db.py`:

| Index Name | Indexed Fields | Purpose |
| :--- | :--- | :--- |
| `_id_` | `_id: 1` | Default unique primary key index. |
| `idx_table_time` | `table_number: 1, reservation_time: 1` | **Compound index** for double-booking overlap checks and table schedules. |
| `idx_reservation_time` | `reservation_time: 1` | Fast BSON Date range queries (`$gte`, `$lt`) and calendar filtering. |
| `idx_customer_email` | `customer_email: 1` | Fast lookup of reservations by customer email. |
| `idx_status` | `status: 1` | Filtering active, seated, and completed reservations. |

### How to Inspect Indexes
In Python:
```python
from database import get_reservations_collection
indexes = get_reservations_collection().index_information()
print(indexes)
```

In `mongosh`:
```javascript
use restaurant_db
db.reservations.getIndexes()
```

---

## 11. Sample Data Generation

Run the seed script to insert fictional reservations:
```powershell
python scripts/seed_data.py
```

### Idempotency & Duplicate Prevention
`scripts/seed_data.py` inspects the compound key `(customer_email, reservation_time)` before performing each insertion. If a reservation with matching email and date already exists, it is skipped. Running the script multiple times is guaranteed never to generate duplicate records.

---

## 12. Testing Suite & Verification

The test suite executes against the live MongoDB instance:

### Running Domain & Database Tests:
```powershell
python tests/test_reservation_system.py
```
**Tests Covered:**
- MongoDB ping and connection health
- Index inspection and compound key verification
- Schema validation rejections (missing fields, negative tables/guests, invalid status)
- `insert_one()`, `find_one()`, and `find()` operations
- `update_one()` with updated party size and special notes
- Double-booking collision rejection (conflicts blocked, valid bookings allowed)
- Soft-delete cancellation and verifying table becomes free immediately
- Hard delete (`delete_one`) verification
- Date range query with `$gte` and `$lt`
- Aggregation pipelines (`$group`, `$sort`) for status and table summaries

### Running REST API Integration Tests:
```powershell
python tests/test_api_endpoints.py
```
**Endpoints Tested:**
- `GET /api/health`
- `POST /api/reservations`
- `GET /api/reservations/<id>`
- `GET /api/reservations/check-availability`
- `PUT /api/reservations/<id>`
- `PATCH /api/reservations/<id>/cancel`
- `GET /api/analytics/summary`

### Run All Tests Simultaneously:
```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```
*(All 19 tests pass with 100% success).*

---

## 13. Database Inspection (mongosh & Compass)

### Using MongoDB Compass (GUI)
1. Open MongoDB Compass.
2. In the connection bar, enter: `mongodb://localhost:27017` and click **Connect**.
3. Select database `restaurant_db` and click collection `reservations`.
4. Navigate to:
   - **Documents:** View live documents with BSON types (`Date`, `Int32`, `String`).
   - **Indexes:** View all 5 active indexes.
   - **Validation:** Inspect the configured JSON Schema validation rules.
   - **Aggregations:** Run pipelines visually using the stage builder.

### Using `mongosh` (CLI Shell)
```bash
# Connect to restaurant_db
mongosh "mongodb://localhost:27017/restaurant_db"

# Count all reservations
db.reservations.countDocuments()

# Find all confirmed reservations sorted by date
db.reservations.find({ status: "confirmed" }).sort({ reservation_time: 1 }).pretty()

# Inspect collection validator
db.getCollectionInfos({ name: "reservations" })[0].options.validator

# Test schema validation failure in shell:
db.reservations.insertOne({
  customer_name: "Illegal Record",
  guests: -5,
  table_number: 1,
  customer_email: "bad@example.com",
  customer_phone: "+15551234",
  reservation_time: new Date(),
  status: "confirmed"
})
// Will throw: Document failed validation
```

---

## 14. Security & Credentials Management

1. **Environment Separation:**
   - Secret keys and database URIs reside in `.env`.
   - `.env` is excluded from git version control via `.gitignore`.
   - Only `.env.example` is committed to version control.
2. **Access Control (Least Privilege):**
   - For production, create dedicated MongoDB users restricted to `readWrite` on `restaurant_db` rather than `root` or `dbAdminAnyDatabase`.
3. **Transport Security (TLS/SSL):**
   - When connecting to MongoDB Atlas or production clusters, PyMongo automatically enforces TLS encryption (`ssl=true`).
4. **Credential Masking:**
   - `database.py` includes `sanitize_uri()`, ensuring passwords and credentials are never printed to terminal logs or system health endpoints.

---

## 15. Deliverables Summary

- Full Flask Web Backend: [app.py](file:///c:/Users/Sajit/OneDrive/Documents/antigravity/app.py)
- PyMongo Connection & Schema Validator: [database.py](file:///c:/Users/Sajit/OneDrive/Documents/antigravity/database.py)
- Service Layer (CRUD, Overlap, Aggregation): [services/reservation_service.py](file:///c:/Users/Sajit/OneDrive/Documents/antigravity/services/reservation_service.py)
- Interactive Frontend UI: [templates/index.html](file:///c:/Users/Sajit/OneDrive/Documents/antigravity/templates/index.html), [style.css](file:///c:/Users/Sajit/OneDrive/Documents/antigravity/static/css/style.css), [app.js](file:///c:/Users/Sajit/OneDrive/Documents/antigravity/static/js/app.js)
- Safe Initialization Script: [scripts/init_db.py](file:///c:/Users/Sajit/OneDrive/Documents/antigravity/scripts/init_db.py)
- Duplicate-Safe Seed Script: [scripts/seed_data.py](file:///c:/Users/Sajit/OneDrive/Documents/antigravity/scripts/seed_data.py)
- Automated Test Suite: [tests/test_reservation_system.py](file:///c:/Users/Sajit/OneDrive/Documents/antigravity/tests/test_reservation_system.py), [tests/test_api_endpoints.py](file:///c:/Users/Sajit/OneDrive/Documents/antigravity/tests/test_api_endpoints.py)
- Configuration: [config.py](file:///c:/Users/Sajit/OneDrive/Documents/antigravity/config.py), [.env.example](file:///c:/Users/Sajit/OneDrive/Documents/antigravity/.env.example), [.gitignore](file:///c:/Users/Sajit/OneDrive/Documents/antigravity/.gitignore), [requirements.txt](file:///c:/Users/Sajit/OneDrive/Documents/antigravity/requirements.txt)
- Complete Project Zip Archive: `restaurant_reservation_system.zip`

