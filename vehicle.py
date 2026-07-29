"""
models/vehicle.py
Defines the Vehicle class along with the valid vehicle types.
"""

VEHICLE_TYPES = ("CAR", "MOTORCYCLE", "EV_CAR")


class Vehicle:
    """Represents a registered vehicle, keyed by its license plate."""

    def __init__(self, license_plate, owner_name, vehicle_type, registered_date):
        self.license_plate = license_plate
        self.owner_name = owner_name
        self.vehicle_type = vehicle_type
        self.registered_date = registered_date

    def to_dict(self):
        return {
            "license_plate": self.license_plate,
            "owner_name": self.owner_name,
            "vehicle_type": self.vehicle_type,
            "registered_date": self.registered_date,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            license_plate=data["license_plate"],
            owner_name=data["owner_name"],
            vehicle_type=data["vehicle_type"],
            registered_date=data["registered_date"],
        )

    def __str__(self):
        return f"{self.license_plate} - {self.owner_name} ({self.vehicle_type})"
