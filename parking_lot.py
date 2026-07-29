"""
models/parking_lot.py
Defines the ParkingLot class.
"""


class ParkingLot:
    """Represents a single physical parking lot / facility location."""

    def __init__(self, lot_id, name, location, spot_ids=None):
        self.lot_id = lot_id
        self.name = name
        self.location = location
        self.spot_ids = spot_ids if spot_ids is not None else []

    def to_dict(self):
        return {
            "lot_id": self.lot_id,
            "name": self.name,
            "location": self.location,
            "spot_ids": self.spot_ids,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            lot_id=data["lot_id"],
            name=data["name"],
            location=data["location"],
            spot_ids=data.get("spot_ids", []),
        )

    def __str__(self):
        return f"[{self.lot_id}] {self.name} ({self.location}) - {len(self.spot_ids)} spot(s)"
