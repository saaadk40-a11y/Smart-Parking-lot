"""
facility_manager.py
The FacilityManager class is the single owner of all filesystem access
and all business logic for the Smart Parking Lot & EV Charging Station
Management System. The CLI (main.py) and the REST API (api.py) both
call into this class rather than duplicating logic.
"""

import os
import json
import csv
import tempfile
from datetime import datetime

from models.parking_lot import ParkingLot
from models.parking_spot import ParkingSpot, SPOT_TYPES, SPOT_STATUSES
from models.vehicle import Vehicle, VEHICLE_TYPES
from models.parking_session import ParkingSession
from models.charging_session import ChargingSession

from exceptions import (
    ValidationError,
    DuplicateLotError,
    DuplicateSpotError,
    DuplicatePlateError,
    LotNotFoundError,
    SpotNotFoundError,
    VehicleNotFoundError,
    SessionNotFoundError,
    ChargingSessionNotFoundError,
    VehicleAlreadyCheckedInError,
    IncompatibleSpotTypeError,
    NoAvailableSpotError,
    SessionAlreadyCompletedError,
    InvalidSpotTypeForChargingError,
    ChargingSessionAlreadyActiveError,
    ChargingSessionNotActiveError,
    SpotOccupiedError,
    InvalidRateError,
    ActiveChargingSessionError,
)

# Which vehicle types may use which spot types.
COMPATIBILITY = {
    "CAR": ["REGULAR", "HANDICAPPED"],
    "MOTORCYCLE": ["REGULAR"],
    "EV_CAR": ["REGULAR", "HANDICAPPED", "EV"],
}


class FacilityManager:
    """Central manager for the entire parking facility."""

    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

        self.lots_file = os.path.join(data_dir, "lots.json")
        self.spots_file = os.path.join(data_dir, "spots.json")
        self.vehicles_file = os.path.join(data_dir, "vehicles.json")
        self.parking_sessions_file = os.path.join(data_dir, "parking_sessions.json")
        self.charging_sessions_file = os.path.join(data_dir, "charging_sessions.json")

        self.lots = {}
        self.spots = {}
        self.vehicles = {}
        self.parking_sessions = {}
        self.charging_sessions = {}

        self._load_all()

    # ------------------------------------------------------------------
    # Atomic JSON file handling
    # ------------------------------------------------------------------
    @staticmethod
    def _atomic_write(filepath, data):
        """Write JSON atomically: write to a temp file, then replace."""
        directory = os.path.dirname(filepath) or "."
        fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".tmp_", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            os.replace(tmp_path, filepath)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    @staticmethod
    def _load_json(filepath):
        if not os.path.exists(filepath):
            return []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read().strip()
                return json.loads(content) if content else []
        except (json.JSONDecodeError, OSError):
            return []

    def _load_all(self):
        self.lots = {
            d["lot_id"]: ParkingLot.from_dict(d)
            for d in self._load_json(self.lots_file)
        }
        self.spots = {
            d["spot_id"]: ParkingSpot.from_dict(d)
            for d in self._load_json(self.spots_file)
        }
        self.vehicles = {
            d["license_plate"]: Vehicle.from_dict(d)
            for d in self._load_json(self.vehicles_file)
        }
        self.parking_sessions = {
            d["session_id"]: ParkingSession.from_dict(d)
            for d in self._load_json(self.parking_sessions_file)
        }
        self.charging_sessions = {
            d["charging_session_id"]: ChargingSession.from_dict(d)
            for d in self._load_json(self.charging_sessions_file)
        }

    def _save_lots(self):
        self._atomic_write(self.lots_file, [l.to_dict() for l in self.lots.values()])

    def _save_spots(self):
        self._atomic_write(self.spots_file, [s.to_dict() for s in self.spots.values()])

    def _save_vehicles(self):
        self._atomic_write(self.vehicles_file, [v.to_dict() for v in self.vehicles.values()])

    def _save_parking_sessions(self):
        self._atomic_write(
            self.parking_sessions_file,
            [s.to_dict() for s in self.parking_sessions.values()],
        )

    def _save_charging_sessions(self):
        self._atomic_write(
            self.charging_sessions_file,
            [s.to_dict() for s in self.charging_sessions.values()],
        )

    # ------------------------------------------------------------------
    # ID generation
    # ------------------------------------------------------------------
    def _generate_session_id(self):
        max_num = 0
        for sid in self.parking_sessions:
            try:
                max_num = max(max_num, int(str(sid).lstrip("PS")))
            except ValueError:
                continue
        return f"PS{max_num + 1:04d}"

    def _generate_charging_id(self):
        max_num = 0
        for cid in self.charging_sessions:
            try:
                max_num = max(max_num, int(str(cid).lstrip("CS")))
            except ValueError:
                continue
        return f"CS{max_num + 1:04d}"

    # ------------------------------------------------------------------
    # Lots
    # ------------------------------------------------------------------
    def add_lot(self, lot_id, name, location):
        if not lot_id or not str(lot_id).strip():
            raise ValidationError("Lot ID cannot be empty.")
        if not name or not str(name).strip():
            raise ValidationError("Lot name cannot be empty.")
        lot_id = str(lot_id).strip()
        if lot_id in self.lots:
            raise DuplicateLotError(f"Lot ID '{lot_id}' already exists.")

        lot = ParkingLot(lot_id=lot_id, name=name.strip(),
                          location=(location or "").strip(), spot_ids=[])
        self.lots[lot_id] = lot
        self._save_lots()
        return lot

    def list_lots(self):
        """Return each lot along with an occupancy summary."""
        results = []
        for lot in self.lots.values():
            lot_spots = [self.spots[sid] for sid in lot.spot_ids if sid in self.spots]
            summary = {
                "AVAILABLE": sum(1 for s in lot_spots if s.status == "AVAILABLE"),
                "OCCUPIED": sum(1 for s in lot_spots if s.status == "OCCUPIED"),
                "OUT_OF_SERVICE": sum(1 for s in lot_spots if s.status == "OUT_OF_SERVICE"),
            }
            results.append({
                "lot": lot.to_dict(),
                "total_spots": len(lot_spots),
                "occupancy_summary": summary,
            })
        return results

    def get_lot(self, lot_id):
        lot = self.lots.get(str(lot_id))
        if not lot:
            raise LotNotFoundError(f"Lot ID '{lot_id}' not found.")
        return lot

    # ------------------------------------------------------------------
    # Spots
    # ------------------------------------------------------------------
    def add_spot(self, lot_id, spot_id, spot_type, hourly_rate, kwh_rate=None):
        lot = self.get_lot(lot_id)

        if not spot_id or not str(spot_id).strip():
            raise ValidationError("Spot ID cannot be empty.")
        spot_id = str(spot_id).strip()
        if spot_id in self.spots:
            raise DuplicateSpotError(f"Spot ID '{spot_id}' already exists.")

        spot_type = (spot_type or "").strip().upper()
        if spot_type not in SPOT_TYPES:
            raise ValidationError(f"Spot type must be one of {SPOT_TYPES}.")

        try:
            hourly_rate = float(hourly_rate)
        except (TypeError, ValueError):
            raise ValidationError("Hourly rate must be a number.")
        if hourly_rate <= 0:
            raise InvalidRateError("Hourly rate must be greater than zero.")

        if spot_type == "EV":
            try:
                kwh_rate = float(kwh_rate)
            except (TypeError, ValueError):
                raise ValidationError("kWh rate must be a number for EV spots.")
            if kwh_rate <= 0:
                raise InvalidRateError("kWh rate must be greater than zero for EV spots.")
        else:
            kwh_rate = None

        spot = ParkingSpot(
            spot_id=spot_id, lot_id=lot.lot_id, spot_type=spot_type,
            status="AVAILABLE", hourly_rate=hourly_rate, kwh_rate=kwh_rate,
        )
        self.spots[spot_id] = spot
        lot.spot_ids.append(spot_id)
        self._save_spots()
        self._save_lots()
        return spot

    def get_spot(self, spot_id):
        spot = self.spots.get(str(spot_id))
        if not spot:
            raise SpotNotFoundError(f"Spot ID '{spot_id}' not found.")
        return spot

    def update_spot(self, spot_id, status=None, hourly_rate=None, kwh_rate=None):
        spot = self.get_spot(spot_id)

        if status is not None:
            status = status.strip().upper()
            if status not in SPOT_STATUSES:
                raise ValidationError(f"Status must be one of {SPOT_STATUSES}.")
            spot.status = status

        if hourly_rate is not None:
            try:
                hourly_rate = float(hourly_rate)
            except (TypeError, ValueError):
                raise ValidationError("Hourly rate must be a number.")
            if hourly_rate <= 0:
                raise InvalidRateError("Hourly rate must be greater than zero.")
            spot.hourly_rate = hourly_rate

        if kwh_rate is not None:
            if spot.spot_type != "EV":
                raise ValidationError("kWh rate only applies to EV spots.")
            try:
                kwh_rate = float(kwh_rate)
            except (TypeError, ValueError):
                raise ValidationError("kWh rate must be a number.")
            if kwh_rate <= 0:
                raise InvalidRateError("kWh rate must be greater than zero.")
            spot.kwh_rate = kwh_rate

        self._save_spots()
        return spot

    def delete_spot(self, spot_id):
        spot = self.get_spot(spot_id)
        if spot.status == "OCCUPIED":
            raise SpotOccupiedError(f"Cannot delete spot '{spot_id}' — it is currently occupied.")

        del self.spots[spot_id]
        lot = self.lots.get(spot.lot_id)
        if lot and spot_id in lot.spot_ids:
            lot.spot_ids.remove(spot_id)
        self._save_spots()
        self._save_lots()
        return True

    # ------------------------------------------------------------------
    # Vehicles
    # ------------------------------------------------------------------
    def register_vehicle(self, license_plate, owner_name, vehicle_type):
        if not license_plate or not str(license_plate).strip():
            raise ValidationError("License plate cannot be empty.")
        license_plate = str(license_plate).strip().upper()
        if license_plate in self.vehicles:
            raise DuplicatePlateError(f"Vehicle '{license_plate}' is already registered.")
        if not owner_name or not str(owner_name).strip():
            raise ValidationError("Owner name cannot be empty.")

        vehicle_type = (vehicle_type or "").strip().upper()
        if vehicle_type not in VEHICLE_TYPES:
            raise ValidationError(f"Vehicle type must be one of {VEHICLE_TYPES}.")

        vehicle = Vehicle(
            license_plate=license_plate, owner_name=owner_name.strip(),
            vehicle_type=vehicle_type,
            registered_date=datetime.now().strftime("%Y-%m-%d"),
        )
        self.vehicles[license_plate] = vehicle
        self._save_vehicles()
        return vehicle

    def get_vehicle(self, license_plate):
        vehicle = self.vehicles.get(str(license_plate).strip().upper())
        if not vehicle:
            raise VehicleNotFoundError(f"Vehicle '{license_plate}' not found.")
        return vehicle

    # ------------------------------------------------------------------
    # Check-in / Check-out
    # ------------------------------------------------------------------
    def _active_session_for_plate(self, license_plate):
        return next(
            (s for s in self.parking_sessions.values()
             if s.license_plate == license_plate and s.status == "ACTIVE"),
            None,
        )

    def _suggest_spot(self, lot, vehicle_type):
        """Bonus: auto-suggest the first available compatible spot in a lot."""
        compatible_types = COMPATIBILITY.get(vehicle_type, [])
        for sid in lot.spot_ids:
            spot = self.spots.get(sid)
            if spot and spot.status == "AVAILABLE" and spot.spot_type in compatible_types:
                return spot
        return None

    def check_in(self, license_plate, lot_id, spot_id=None):
        license_plate = str(license_plate).strip().upper()
        vehicle = self.get_vehicle(license_plate)
        lot = self.get_lot(lot_id)

        if self._active_session_for_plate(license_plate):
            raise VehicleAlreadyCheckedInError(
                f"Vehicle '{license_plate}' is already checked in elsewhere."
            )

        compatible_types = COMPATIBILITY.get(vehicle.vehicle_type, [])

        if spot_id:
            spot = self.get_spot(spot_id)
            if spot.lot_id != lot.lot_id:
                raise ValidationError(f"Spot '{spot_id}' does not belong to lot '{lot_id}'.")
            if spot.spot_type not in compatible_types:
                raise IncompatibleSpotTypeError(
                    f"Vehicle type '{vehicle.vehicle_type}' cannot use a '{spot.spot_type}' spot."
                )
            if spot.status != "AVAILABLE":
                raise NoAvailableSpotError(f"Spot '{spot_id}' is not available.")
        else:
            spot = self._suggest_spot(lot, vehicle.vehicle_type)
            if not spot:
                raise NoAvailableSpotError(
                    f"No compatible available spot in lot '{lot_id}' for vehicle type "
                    f"'{vehicle.vehicle_type}'."
                )

        session_id = self._generate_session_id()
        session = ParkingSession(
            session_id=session_id, license_plate=license_plate,
            spot_id=spot.spot_id, lot_id=lot.lot_id,
            check_in_time=datetime.now().isoformat(),
            check_out_time=None, parking_fee=None, status="ACTIVE",
        )
        spot.status = "OCCUPIED"
        self.parking_sessions[session_id] = session

        self._save_spots()
        self._save_parking_sessions()
        return session

    def check_out(self, session_id):
        session = self.parking_sessions.get(str(session_id))
        if not session:
            raise SessionNotFoundError(f"Session '{session_id}' not found.")
        if session.status == "COMPLETED":
            raise SessionAlreadyCompletedError(f"Session '{session_id}' is already completed.")

        active_charging = next(
            (c for c in self.charging_sessions.values()
             if c.parking_session_id == session_id and c.status == "ACTIVE"),
            None,
        )
        if active_charging:
            raise ActiveChargingSessionError(
                f"Session '{session_id}' has an active charging session — stop it before checking out."
            )

        spot = self.get_spot(session.spot_id)
        now = datetime.now()
        fee = session.calculate_fee(now, spot.hourly_rate)

        session.parking_fee = fee
        session.check_out_time = now.isoformat()
        session.status = "COMPLETED"
        spot.status = "AVAILABLE"

        self._save_parking_sessions()
        self._save_spots()
        return session

    # ------------------------------------------------------------------
    # Charging sessions
    # ------------------------------------------------------------------
    def start_charging(self, session_id, start_meter=0.0):
        session = self.parking_sessions.get(str(session_id))
        if not session:
            raise SessionNotFoundError(f"Session '{session_id}' not found.")
        if session.status != "ACTIVE":
            raise SessionAlreadyCompletedError(
                f"Session '{session_id}' is not active; cannot start charging."
            )

        spot = self.get_spot(session.spot_id)
        if spot.spot_type != "EV":
            raise InvalidSpotTypeForChargingError(
                f"Spot '{spot.spot_id}' is not an EV spot; charging is not available."
            )

        existing_active = next(
            (c for c in self.charging_sessions.values()
             if c.parking_session_id == session_id and c.status == "ACTIVE"),
            None,
        )
        if existing_active:
            raise ChargingSessionAlreadyActiveError(
                f"Session '{session_id}' already has an active charging session."
            )

        try:
            start_meter = float(start_meter)
        except (TypeError, ValueError):
            raise ValidationError("start_meter must be a number.")
        if start_meter < 0:
            raise ValidationError("start_meter cannot be negative.")

        charging_id = self._generate_charging_id()
        charging_session = ChargingSession(
            charging_session_id=charging_id, parking_session_id=session_id,
            start_time=datetime.now().isoformat(), end_time=None,
            start_meter=start_meter, end_meter=None, energy_cost=None,
            status="ACTIVE",
        )
        self.charging_sessions[charging_id] = charging_session
        self._save_charging_sessions()
        return charging_session

    def stop_charging(self, session_id, end_meter):
        charging_session = next(
            (c for c in self.charging_sessions.values()
             if c.parking_session_id == str(session_id) and c.status == "ACTIVE"),
            None,
        )
        if not charging_session:
            raise ChargingSessionNotActiveError(
                f"No active charging session found for parking session '{session_id}'."
            )

        parking_session = self.parking_sessions.get(str(session_id))
        spot = self.get_spot(parking_session.spot_id)

        try:
            end_meter = float(end_meter)
        except (TypeError, ValueError):
            raise ValidationError("end_meter must be a number.")
        if end_meter < charging_session.start_meter:
            raise ValidationError("end_meter cannot be less than the start meter reading.")

        cost = charging_session.calculate_cost(end_meter, spot.kwh_rate)
        charging_session.end_meter = end_meter
        charging_session.energy_cost = cost
        charging_session.end_time = datetime.now().isoformat()
        charging_session.status = "COMPLETED"

        self._save_charging_sessions()
        return charging_session

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def vehicle_status(self, license_plate):
        license_plate = str(license_plate).strip().upper()
        vehicle = self.get_vehicle(license_plate)
        active_session = self._active_session_for_plate(license_plate)

        if not active_session:
            return {"vehicle": vehicle.to_dict(), "status": "NOT_PARKED"}

        active_charging = next(
            (c for c in self.charging_sessions.values()
             if c.parking_session_id == active_session.session_id and c.status == "ACTIVE"),
            None,
        )
        return {
            "vehicle": vehicle.to_dict(),
            "status": "PARKED",
            "session": active_session.to_dict(),
            "charging_session": active_charging.to_dict() if active_charging else None,
        }

    def active_sessions(self):
        return [s for s in self.parking_sessions.values() if s.status == "ACTIVE"]

    def vehicle_history(self, license_plate):
        license_plate = str(license_plate).strip().upper()
        self.get_vehicle(license_plate)  # raises if not found
        return [
            s for s in self.parking_sessions.values()
            if s.license_plate == license_plate
        ]

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------
    def generate_report(self, filename=None):
        filename = filename or os.path.join(".", "facility_report.txt")

        total_lots = len(self.lots)
        total_spots = len(self.spots)

        by_type = {}
        by_status = {}
        for spot in self.spots.values():
            by_type[spot.spot_type] = by_type.get(spot.spot_type, 0) + 1
            by_status[spot.status] = by_status.get(spot.status, 0) + 1

        parking_revenue = sum(
            s.parking_fee for s in self.parking_sessions.values()
            if s.status == "COMPLETED" and s.parking_fee
        )
        charging_revenue = sum(
            c.energy_cost for c in self.charging_sessions.values()
            if c.status == "COMPLETED" and c.energy_cost
        )

        completed_sessions = [s for s in self.parking_sessions.values() if s.status == "COMPLETED"]
        if completed_sessions:
            total_minutes = 0
            for s in completed_sessions:
                start = datetime.fromisoformat(s.check_in_time)
                end = datetime.fromisoformat(s.check_out_time)
                total_minutes += (end - start).total_seconds() / 60
            avg_duration_minutes = round(total_minutes / len(completed_sessions), 1)
        else:
            avg_duration_minutes = 0.0

        lot_session_counts = {}
        for s in self.parking_sessions.values():
            lot_session_counts[s.lot_id] = lot_session_counts.get(s.lot_id, 0) + 1
        busiest_lot = None
        if lot_session_counts:
            busiest_lot_id = max(lot_session_counts, key=lot_session_counts.get)
            lot_obj = self.lots.get(busiest_lot_id)
            busiest_lot = {
                "lot_id": busiest_lot_id,
                "name": lot_obj.name if lot_obj else "Unknown",
                "session_count": lot_session_counts[busiest_lot_id],
            }

        spend_by_plate = {}
        for s in self.parking_sessions.values():
            if s.parking_fee:
                spend_by_plate[s.license_plate] = spend_by_plate.get(s.license_plate, 0) + s.parking_fee
        for c in self.charging_sessions.values():
            if c.energy_cost:
                parent = self.parking_sessions.get(c.parking_session_id)
                if parent:
                    spend_by_plate[parent.license_plate] = (
                        spend_by_plate.get(parent.license_plate, 0) + c.energy_cost
                    )
        top_vehicles = sorted(spend_by_plate.items(), key=lambda x: x[1], reverse=True)[:3]

        active_sessions_count = sum(1 for s in self.parking_sessions.values() if s.status == "ACTIVE")
        active_charging_count = sum(1 for c in self.charging_sessions.values() if c.status == "ACTIVE")

        lines = []
        lines.append("=" * 60)
        lines.append("        SMART PARKING FACILITY REPORT")
        lines.append("=" * 60)
        lines.append(f"Total Lots:                        {total_lots}")
        lines.append(f"Total Spots:                        {total_spots}")
        lines.append("")
        lines.append("Spots by Type:")
        for t, count in by_type.items():
            lines.append(f"   - {t}: {count}")
        lines.append("")
        lines.append("Spots by Status:")
        for st, count in by_status.items():
            lines.append(f"   - {st}: {count}")
        lines.append("")
        lines.append(f"Parking Revenue:                   ${parking_revenue:.2f}")
        lines.append(f"Charging Revenue:                  ${charging_revenue:.2f}")
        lines.append(f"Total Revenue:                      ${(parking_revenue + charging_revenue):.2f}")
        lines.append("")
        lines.append(f"Average Session Duration (minutes): {avg_duration_minutes}")
        if busiest_lot:
            lines.append(
                f"Busiest Lot:                        {busiest_lot['name']} "
                f"({busiest_lot['lot_id']}) - {busiest_lot['session_count']} session(s)"
            )
        else:
            lines.append("Busiest Lot:                        No sessions yet.")
        lines.append("")
        lines.append("Top 3 Vehicles by Spend:")
        if top_vehicles:
            for plate, total in top_vehicles:
                lines.append(f"   - {plate}: ${total:.2f}")
        else:
            lines.append("   (No completed sessions yet)")
        lines.append("")
        lines.append(f"Active Sessions:                    {active_sessions_count}")
        lines.append(f"Active Charging Sessions:           {active_charging_count}")
        lines.append("")
        lines.append(f"Report Generated On:                {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 60)

        report_text = "\n".join(lines)
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(report_text)
        except OSError as e:
            print(f"[Error] Could not write report: {e}")

        return {
            "text": report_text,
            "total_lots": total_lots,
            "total_spots": total_spots,
            "spots_by_type": by_type,
            "spots_by_status": by_status,
            "parking_revenue": round(parking_revenue, 2),
            "charging_revenue": round(charging_revenue, 2),
            "total_revenue": round(parking_revenue + charging_revenue, 2),
            "average_session_duration_minutes": avg_duration_minutes,
            "busiest_lot": busiest_lot,
            "top_vehicles": [{"license_plate": p, "total_spent": round(t, 2)} for p, t in top_vehicles],
            "active_sessions": active_sessions_count,
            "active_charging_sessions": active_charging_count,
            "generated_at": datetime.now().isoformat(),
        }

    # ------------------------------------------------------------------
    # Bonus features
    # ------------------------------------------------------------------
    def export_sessions_csv(self, filename="sessions_export.csv"):
        try:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Session ID", "License Plate", "Spot ID", "Lot ID",
                    "Check-in", "Check-out", "Parking Fee", "Status",
                ])
                for s in self.parking_sessions.values():
                    writer.writerow([
                        s.session_id, s.license_plate, s.spot_id, s.lot_id,
                        s.check_in_time, s.check_out_time or "", s.parking_fee or "",
                        s.status,
                    ])
            return filename
        except OSError as e:
            raise ValidationError(f"Could not export CSV: {e}")

    def occupancy_dashboard(self, bar_width=20):
        """Return an ASCII bar-chart string of occupancy per lot."""
        lines = ["Lot Occupancy Dashboard", "-" * 40]
        for lot in self.lots.values():
            lot_spots = [self.spots[sid] for sid in lot.spot_ids if sid in self.spots]
            total = len(lot_spots)
            occupied = sum(1 for s in lot_spots if s.status == "OCCUPIED")
            ratio = (occupied / total) if total else 0
            filled = int(ratio * bar_width)
            bar = "#" * filled + "-" * (bar_width - filled)
            pct = round(ratio * 100, 1)
            lines.append(f"{lot.name[:15]:<15} [{bar}] {occupied}/{total} ({pct}%)")
        return "\n".join(lines)
