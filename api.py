"""
api.py
Flask REST API layer for the Smart Parking Lot & EV Charging Station
Management System. This module contains NO business logic of its own —
it only validates the shape of incoming requests, calls into
FacilityManager, and translates the result (or any FacilityError) into
an HTTP response with the correct status code and a structured JSON
error body. Raw stack traces never reach the client.
"""

from flask import Flask, request, jsonify, Response

from facility_manager import FacilityManager
from exceptions import FacilityError, ValidationError

app = Flask(__name__)
fm = FacilityManager("data")


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def get_json_body():
    """Return the parsed JSON body, or raise ValidationError if missing/invalid."""
    data = request.get_json(silent=True)
    if data is None:
        raise ValidationError("Request body must be valid JSON.")
    return data


def require_fields(data, fields):
    """Raise ValidationError if any required field is missing from data."""
    missing = [f for f in fields if data.get(f) in (None, "")]
    if missing:
        raise ValidationError(f"Missing required field(s): {', '.join(missing)}")


# ----------------------------------------------------------------------
# Error handlers — every FacilityError maps to its declared HTTP status.
# Anything unexpected becomes a generic 500 with no stack trace leaked.
# ----------------------------------------------------------------------
@app.errorhandler(FacilityError)
def handle_facility_error(err):
    return jsonify({
        "error": type(err).__name__,
        "message": str(err),
    }), err.http_status


@app.errorhandler(404)
def handle_404(err):
    return jsonify({"error": "NotFound", "message": "The requested resource was not found."}), 404


@app.errorhandler(405)
def handle_405(err):
    return jsonify({"error": "MethodNotAllowed", "message": "HTTP method not allowed on this endpoint."}), 405


@app.errorhandler(Exception)
def handle_unexpected(err):
    app.logger.exception("Unexpected error")
    return jsonify({"error": "InternalServerError", "message": "An unexpected error occurred."}), 500


# ----------------------------------------------------------------------
# Lots
# ----------------------------------------------------------------------
@app.route("/lots", methods=["POST"])
def create_lot():
    data = get_json_body()
    require_fields(data, ["lot_id", "name"])
    lot = fm.add_lot(data["lot_id"], data["name"], data.get("location", ""))
    return jsonify(lot.to_dict()), 201


@app.route("/lots", methods=["GET"])
def list_lots():
    return jsonify(fm.list_lots()), 200


# ----------------------------------------------------------------------
# Spots
# ----------------------------------------------------------------------
@app.route("/lots/<lot_id>/spots", methods=["POST"])
def add_spot(lot_id):
    data = get_json_body()
    require_fields(data, ["spot_id", "spot_type", "hourly_rate"])
    spot = fm.add_spot(
        lot_id, data["spot_id"], data["spot_type"],
        data["hourly_rate"], data.get("kwh_rate"),
    )
    return jsonify(spot.to_dict()), 201


@app.route("/spots/<spot_id>", methods=["GET"])
def get_spot(spot_id):
    spot = fm.get_spot(spot_id)
    return jsonify(spot.to_dict()), 200


@app.route("/spots/<spot_id>", methods=["PATCH"])
def update_spot(spot_id):
    data = get_json_body()
    spot = fm.update_spot(
        spot_id,
        status=data.get("status"),
        hourly_rate=data.get("hourly_rate"),
        kwh_rate=data.get("kwh_rate"),
    )
    return jsonify(spot.to_dict()), 200


@app.route("/spots/<spot_id>", methods=["DELETE"])
def delete_spot(spot_id):
    fm.delete_spot(spot_id)
    return jsonify({"message": f"Spot '{spot_id}' deleted successfully."}), 200


# ----------------------------------------------------------------------
# Vehicles
# ----------------------------------------------------------------------
@app.route("/vehicles", methods=["POST"])
def register_vehicle():
    data = get_json_body()
    require_fields(data, ["license_plate", "owner_name", "vehicle_type"])
    vehicle = fm.register_vehicle(
        data["license_plate"], data["owner_name"], data["vehicle_type"]
    )
    return jsonify(vehicle.to_dict()), 201


@app.route("/vehicles/<plate>/status", methods=["GET"])
def vehicle_status(plate):
    return jsonify(fm.vehicle_status(plate)), 200


@app.route("/vehicles/<plate>/history", methods=["GET"])
def vehicle_history(plate):
    history = fm.vehicle_history(plate)
    return jsonify([s.to_dict() for s in history]), 200


# ----------------------------------------------------------------------
# Parking sessions
# ----------------------------------------------------------------------
@app.route("/sessions/check-in", methods=["POST"])
def check_in():
    data = get_json_body()
    require_fields(data, ["license_plate", "lot_id"])
    session = fm.check_in(data["license_plate"], data["lot_id"], data.get("spot_id"))
    return jsonify(session.to_dict()), 201


@app.route("/sessions/<session_id>/check-out", methods=["POST"])
def check_out(session_id):
    session = fm.check_out(session_id)
    return jsonify(session.to_dict()), 200


@app.route("/sessions/active", methods=["GET"])
def active_sessions():
    sessions = fm.active_sessions()
    return jsonify([s.to_dict() for s in sessions]), 200


# ----------------------------------------------------------------------
# Charging sessions
# ----------------------------------------------------------------------
@app.route("/sessions/<session_id>/charging/start", methods=["POST"])
def start_charging(session_id):
    data = get_json_body() if request.data else {}
    start_meter = data.get("start_meter", 0.0)
    charging_session = fm.start_charging(session_id, start_meter)
    return jsonify(charging_session.to_dict()), 201


@app.route("/sessions/<session_id>/charging/stop", methods=["POST"])
def stop_charging(session_id):
    data = get_json_body()
    require_fields(data, ["end_meter"])
    charging_session = fm.stop_charging(session_id, data["end_meter"])
    return jsonify(charging_session.to_dict()), 200


# ----------------------------------------------------------------------
# Reporting
# ----------------------------------------------------------------------
@app.route("/report", methods=["GET"])
def report():
    result = fm.generate_report("facility_report.txt")
    result.pop("text", None)  # keep the JSON response summary-only
    return jsonify(result), 200


# ----------------------------------------------------------------------
# Bonus endpoints
# ----------------------------------------------------------------------
@app.route("/occupancy/dashboard", methods=["GET"])
def occupancy_dashboard():
    return Response(fm.occupancy_dashboard(), mimetype="text/plain"), 200


@app.route("/sessions/export", methods=["GET"])
def export_sessions():
    filename = fm.export_sessions_csv("sessions_export.csv")
    with open(filename, "r", encoding="utf-8") as f:
        csv_data = f.read()
    return Response(
        csv_data, mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    ), 200


@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "service": "Smart Parking Lot & EV Charging Station Management System",
        "status": "running",
    }), 200


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
