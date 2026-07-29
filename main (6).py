"""
main.py
CLI entry point for the Smart Parking Lot & EV Charging Station
Management System. Mirrors the same functionality exposed by api.py,
all routed through the shared FacilityManager.
"""

from facility_manager import FacilityManager
from exceptions import FacilityError

MENU = """
========== Smart Parking Facility Management ==========
1. Add Parking Lot
2. Add Parking Spot
3. View All Lots (with occupancy)
4. Register Vehicle
5. Check In Vehicle
6. Check Out Vehicle
7. Start Charging Session
8. Stop Charging Session
9. Search Vehicle Status (by License Plate)
10. View Active Sessions
11. View Vehicle History
12. Update Spot (status / rates)
13. Delete Spot
14. Generate Facility Report
15. Occupancy Dashboard (bonus)
16. Export Sessions to CSV (bonus)
17. Exit
=========================================================
"""


def add_lot_flow(fm):
    print("\n-- Add Parking Lot --")
    lot_id = input("Lot ID: ").strip()
    name = input("Name: ").strip()
    location = input("Location: ").strip()
    lot = fm.add_lot(lot_id, name, location)
    print(f"Lot added: {lot}")


def add_spot_flow(fm):
    print("\n-- Add Parking Spot --")
    lot_id = input("Lot ID: ").strip()
    spot_id = input("Spot ID: ").strip()
    spot_type = input("Spot Type (REGULAR / HANDICAPPED / EV): ").strip().upper()
    hourly_rate = input("Hourly Rate: ").strip()
    kwh_rate = None
    if spot_type == "EV":
        kwh_rate = input("kWh Rate: ").strip()
    spot = fm.add_spot(lot_id, spot_id, spot_type, hourly_rate, kwh_rate)
    print(f"Spot added: {spot}")


def view_lots_flow(fm):
    print("\n-- All Lots --")
    lots = fm.list_lots()
    if not lots:
        print("No lots yet.")
        return
    for entry in lots:
        lot = entry["lot"]
        summary = entry["occupancy_summary"]
        print(
            f"[{lot['lot_id']}] {lot['name']} ({lot['location']}) - "
            f"Total: {entry['total_spots']} | Available: {summary['AVAILABLE']} | "
            f"Occupied: {summary['OCCUPIED']} | Out of Service: {summary['OUT_OF_SERVICE']}"
        )


def register_vehicle_flow(fm):
    print("\n-- Register Vehicle --")
    plate = input("License Plate: ").strip()
    owner = input("Owner Name: ").strip()
    vtype = input("Vehicle Type (CAR / MOTORCYCLE / EV_CAR): ").strip().upper()
    vehicle = fm.register_vehicle(plate, owner, vtype)
    print(f"Vehicle registered: {vehicle}")


def check_in_flow(fm):
    print("\n-- Check In Vehicle --")
    plate = input("License Plate: ").strip()
    lot_id = input("Lot ID: ").strip()
    spot_id = input("Spot ID (leave blank to auto-assign): ").strip()
    session = fm.check_in(plate, lot_id, spot_id or None)
    print(f"Checked in: {session}")


def check_out_flow(fm):
    print("\n-- Check Out Vehicle --")
    session_id = input("Session ID: ").strip()
    session = fm.check_out(session_id)
    print(f"Checked out: {session}")


def start_charging_flow(fm):
    print("\n-- Start Charging Session --")
    session_id = input("Session ID: ").strip()
    start_meter = input("Start Meter Reading (kWh): ").strip()
    cs = fm.start_charging(session_id, start_meter or 0.0)
    print(f"Charging started: {cs}")


def stop_charging_flow(fm):
    print("\n-- Stop Charging Session --")
    session_id = input("Session ID: ").strip()
    end_meter = input("End Meter Reading (kWh): ").strip()
    cs = fm.stop_charging(session_id, end_meter)
    print(f"Charging stopped: {cs}")


def vehicle_status_flow(fm):
    print("\n-- Vehicle Status --")
    plate = input("License Plate: ").strip()
    status = fm.vehicle_status(plate)
    print(status)


def active_sessions_flow(fm):
    print("\n-- Active Sessions --")
    sessions = fm.active_sessions()
    if not sessions:
        print("No active sessions.")
        return
    for s in sessions:
        print(s)


def vehicle_history_flow(fm):
    print("\n-- Vehicle History --")
    plate = input("License Plate: ").strip()
    history = fm.vehicle_history(plate)
    if not history:
        print("No session history for this vehicle.")
        return
    for s in history:
        print(s)


def update_spot_flow(fm):
    print("\n-- Update Spot --")
    spot_id = input("Spot ID: ").strip()
    status = input("New Status (AVAILABLE / OCCUPIED / OUT_OF_SERVICE, blank to skip): ").strip()
    hourly_rate = input("New Hourly Rate (blank to skip): ").strip()
    kwh_rate = input("New kWh Rate (blank to skip): ").strip()
    spot = fm.update_spot(
        spot_id,
        status=status or None,
        hourly_rate=hourly_rate or None,
        kwh_rate=kwh_rate or None,
    )
    print(f"Spot updated: {spot}")


def delete_spot_flow(fm):
    print("\n-- Delete Spot --")
    spot_id = input("Spot ID: ").strip()
    fm.delete_spot(spot_id)
    print("Spot deleted successfully.")


def generate_report_flow(fm):
    print("\n-- Generating Report --")
    report = fm.generate_report("facility_report.txt")
    print(report["text"])
    print("\nReport saved to facility_report.txt")


def occupancy_dashboard_flow(fm):
    print("\n-- Occupancy Dashboard --")
    print(fm.occupancy_dashboard())


def export_csv_flow(fm):
    print("\n-- Export Sessions to CSV --")
    filename = fm.export_sessions_csv("sessions_export.csv")
    print(f"Exported to {filename}")


def main():
    fm = FacilityManager("data")

    actions = {
        "1": lambda: add_lot_flow(fm),
        "2": lambda: add_spot_flow(fm),
        "3": lambda: view_lots_flow(fm),
        "4": lambda: register_vehicle_flow(fm),
        "5": lambda: check_in_flow(fm),
        "6": lambda: check_out_flow(fm),
        "7": lambda: start_charging_flow(fm),
        "8": lambda: stop_charging_flow(fm),
        "9": lambda: vehicle_status_flow(fm),
        "10": lambda: active_sessions_flow(fm),
        "11": lambda: vehicle_history_flow(fm),
        "12": lambda: update_spot_flow(fm),
        "13": lambda: delete_spot_flow(fm),
        "14": lambda: generate_report_flow(fm),
        "15": lambda: occupancy_dashboard_flow(fm),
        "16": lambda: export_csv_flow(fm),
    }

    while True:
        print(MENU)
        choice = input("Enter your choice: ").strip()

        if choice == "17":
            print("Shutting down. Goodbye!")
            break

        action = actions.get(choice)
        if not action:
            print("Invalid choice. Please select a valid menu option.")
            continue

        try:
            action()
        except FacilityError as e:
            print(f"[Error] {e}")
        except Exception as e:
            print(f"[Unexpected Error] {e}")


if __name__ == "__main__":
    main()
