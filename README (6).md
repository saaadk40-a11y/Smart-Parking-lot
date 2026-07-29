# Smart Parking Lot & EV Charging Station Management System

A Python backend for managing a multi-lot parking facility with mixed
spot types (Regular, Handicapped, EV Charging). Supports vehicle
check-in/check-out, dynamic time-based billing, kWh-based EV charging
billing, and exposes all functionality both as a **CLI menu** and a
**REST API** (Flask), built on the same OOP + JSON persistence +
exception-handling foundation used in the earlier Library Management
System project.

## Features

- Manage multiple parking lots, each with Regular, Handicapped, and EV spots
- Register vehicles (Car, Motorcycle, EV Car) with owner details
- Check in a vehicle to a specific spot, or auto-assign the nearest
  available compatible spot
- Check out a vehicle with automatic time-based billing
- Start/stop EV charging sessions with kWh-based billing
- Search a vehicle's current status by license plate
- View all active sessions across the facility
- View full session history for any vehicle
- Update spot metadata (status, rates) or mark a spot out of service
- Delete a spot (blocked while occupied)
- Generate a full facility report (`facility_report.txt`)
- **Every action above is available both via the CLI and via REST endpoints**
- Atomic JSON writes (write-to-temp-then-replace) so a crash mid-write
  can never corrupt a data file
- Custom exception hierarchy mapped to precise HTTP status codes —
  never a raw 500 stack trace

### Bonus features implemented

1. **CSV export** of all parking sessions (`/sessions/export` or CLI option 16)
2. **Auto-suggestion** of the nearest available compatible spot when
   checking in without specifying a `spot_id`
3. **ASCII bar-chart occupancy dashboard** (`/occupancy/dashboard` or CLI option 15)
4. **Pytest suite** covering billing calculations and every exception path (`tests/test_facility.py`)
5. **Dockerized API** (`Dockerfile` + `docker-compose.yml`)

## Technologies Used

- Python 3
- Flask (REST API layer)
- Standard library: `json`, `os`, `csv`, `tempfile`, `datetime`
- Object-Oriented Programming (5 model classes + `FacilityManager`)
- Custom exception hierarchy, each mapped to an HTTP status code
- Pytest (bonus test suite)
- Docker / Docker Compose (bonus containerization)

## Domain Model

| Class | Key fields |
|---|---|
| `ParkingLot` | `lot_id`, `name`, `location`, `spot_ids` |
| `ParkingSpot` | `spot_id`, `lot_id`, `spot_type` (REGULAR/HANDICAPPED/EV), `status` (AVAILABLE/OCCUPIED/OUT_OF_SERVICE), `hourly_rate`, `kwh_rate` (EV only) |
| `Vehicle` | `license_plate`, `owner_name`, `vehicle_type` (CAR/MOTORCYCLE/EV_CAR), `registered_date` |
| `ParkingSession` | `session_id`, `license_plate`, `spot_id`, `lot_id`, `check_in_time`, `check_out_time`, `parking_fee`, `status` (ACTIVE/COMPLETED) |
| `ChargingSession` | `charging_session_id`, `parking_session_id`, `start_time`, `end_time`, `start_meter`, `end_meter`, `energy_cost`, `status` (ACTIVE/COMPLETED) |

**Spot/vehicle compatibility** (enforced on check-in):
- `MOTORCYCLE` → `REGULAR` only
- `CAR` → `REGULAR` or `HANDICAPPED`
- `EV_CAR` → `REGULAR`, `HANDICAPPED`, or `EV`

## Billing Rules

**Parking fee:**
- First 10 minutes are a grace period — no charge at all.
- Beyond that, elapsed time is rounded **up** to the next full hour and
  multiplied by the spot's hourly rate.
- Any hours beyond the first 24 are billed at **1.5×** the normal rate
  (overstay surcharge).
- Example: a 26h15m stay at $5/hr = 24h × $5 + 3h (rounded up from 2h15m) × $5 × 1.5 = $120 + $22.50 = **$142.50**

**EV charging cost:**
- `(end_meter − start_meter) × spot.kwh_rate`
- A parking session **cannot** be checked out while it has an active
  charging session — the charging session must be stopped first.

## How to Run

### CLI

```bash
pip install -r requirements.txt
python3 main.py
```

### REST API

```bash
pip install -r requirements.txt
python3 api.py
```

The API starts on `http://localhost:5000`.

### With Docker

```bash
docker-compose up --build
```

### Running tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

## API Reference

All responses are JSON. Errors follow this shape:

```json
{ "error": "IncompatibleSpotTypeError", "message": "Vehicle type 'MOTORCYCLE' cannot use a 'HANDICAPPED' spot." }
```

| Method | Endpoint | Description | Success | Common errors |
|---|---|---|---|---|
| POST | `/lots` | Create a lot | 201 | 400 missing fields, 409 duplicate |
| GET | `/lots` | List all lots with occupancy summary | 200 | — |
| POST | `/lots/{lot_id}/spots` | Add a spot to a lot | 201 | 400, 404 lot not found, 409 duplicate |
| GET | `/spots/{spot_id}` | Get spot detail | 200 | 404 |
| PATCH | `/spots/{spot_id}` | Update spot status/rates | 200 | 400, 404 |
| DELETE | `/spots/{spot_id}` | Delete a spot | 200 | 404, 409 occupied |
| POST | `/vehicles` | Register a vehicle | 201 | 400, 409 duplicate plate |
| GET | `/vehicles/{plate}/status` | Current status of a vehicle | 200 | 404 |
| GET | `/vehicles/{plate}/history` | Full session history | 200 | 404 |
| POST | `/sessions/check-in` | Check in a vehicle | 201 | 400, 404, 409 |
| POST | `/sessions/{session_id}/check-out` | Check out & bill | 200 | 404, 409 |
| GET | `/sessions/active` | List active sessions | 200 | — |
| POST | `/sessions/{session_id}/charging/start` | Start EV charging | 201 | 400, 404, 409 |
| POST | `/sessions/{session_id}/charging/stop` | Stop EV charging & bill | 200 | 400, 404, 409 |
| GET | `/report` | Generate & return facility report summary | 200 | — |
| GET | `/occupancy/dashboard` | ASCII bar-chart occupancy (bonus) | 200 | — |
| GET | `/sessions/export` | Download all sessions as CSV (bonus) | 200 | — |

### Sample requests (curl)

Create a lot:
```bash
curl -X POST http://localhost:5000/lots \
  -H "Content-Type: application/json" \
  -d '{"lot_id": "L1", "name": "Downtown Garage", "location": "123 Main St"}'
```

Add an EV spot:
```bash
curl -X POST http://localhost:5000/lots/L1/spots \
  -H "Content-Type: application/json" \
  -d '{"spot_id": "S4", "spot_type": "EV", "hourly_rate": 6.0, "kwh_rate": 0.35}'
```

Register a vehicle:
```bash
curl -X POST http://localhost:5000/vehicles \
  -H "Content-Type: application/json" \
  -d '{"license_plate": "ABC123", "owner_name": "John Doe", "vehicle_type": "CAR"}'
```

Check in (auto-assign a spot by omitting `spot_id`):
```bash
curl -X POST http://localhost:5000/sessions/check-in \
  -H "Content-Type: application/json" \
  -d '{"license_plate": "ABC123", "lot_id": "L1"}'
```

Start charging:
```bash
curl -X POST http://localhost:5000/sessions/PS0001/charging/start \
  -H "Content-Type: application/json" \
  -d '{"start_meter": 5.0}'
```

Stop charging:
```bash
curl -X POST http://localhost:5000/sessions/PS0001/charging/stop \
  -H "Content-Type: application/json" \
  -d '{"end_meter": 30.0}'
```

Check out:
```bash
curl -X POST http://localhost:5000/sessions/PS0001/check-out
```

Get the occupancy dashboard:
```bash
curl http://localhost:5000/occupancy/dashboard
```

## Folder Structure

```
SmartParkingSystem/
│── main.py                  # CLI entry point
│── api.py                   # Flask REST layer
│── models/
│   │── parking_lot.py
│   │── parking_spot.py
│   │── vehicle.py
│   │── parking_session.py
│   │── charging_session.py
│── facility_manager.py       # All business logic + JSON persistence
│── exceptions.py             # Custom exception hierarchy
│── tests/
│   └── test_facility.py      # Pytest: billing logic + exception paths
│── data/
│   │── lots.json
│   │── spots.json
│   │── vehicles.json
│   │── parking_sessions.json
│   │── charging_sessions.json
│── facility_report.txt
│── sessions_export.csv
│── requirements.txt
│── Dockerfile
│── docker-compose.yml
│── README.md
```

## Design Notes

- `FacilityManager` is the **only** class that touches the filesystem —
  both `main.py` (CLI) and `api.py` (REST) call into it and never
  duplicate business logic.
- Every JSON write is atomic: data is written to a temp file in the
  same directory, then swapped in with `os.replace()`, so a crash
  mid-write can't leave a half-written, corrupted file.
- Every domain rule violation raises a specific exception (never a
  bare `Exception`), each carrying an `http_status` attribute so
  `api.py` can map it to the correct HTTP response without an if/elif
  chain per error type.
- Session and charging IDs (`PS0001`, `CS0001`, ...) are auto-generated
  sequentially; Lot IDs, Spot IDs, and License Plates are supplied by
  the caller and validated for uniqueness.
