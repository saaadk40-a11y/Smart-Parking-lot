"""
exceptions.py
Custom exception hierarchy for the Smart Parking Lot & EV Charging
Station Management System. Every domain rule violation raises one of
these instead of a bare Exception, so the API layer can map each to a
precise HTTP status code.
"""


class FacilityError(Exception):
    """Base class for all facility-related errors."""
    http_status = 400


class ValidationError(FacilityError):
    """Raised for malformed or missing required fields."""
    http_status = 400


class DuplicateLotError(FacilityError):
    http_status = 409


class DuplicateSpotError(FacilityError):
    http_status = 409


class DuplicatePlateError(FacilityError):
    http_status = 409


class LotNotFoundError(FacilityError):
    http_status = 404


class SpotNotFoundError(FacilityError):
    http_status = 404


class VehicleNotFoundError(FacilityError):
    http_status = 404


class SessionNotFoundError(FacilityError):
    http_status = 404


class ChargingSessionNotFoundError(FacilityError):
    http_status = 404


class VehicleAlreadyCheckedInError(FacilityError):
    http_status = 409


class IncompatibleSpotTypeError(FacilityError):
    http_status = 400


class NoAvailableSpotError(FacilityError):
    http_status = 409


class SessionAlreadyCompletedError(FacilityError):
    http_status = 409


class InvalidSpotTypeForChargingError(FacilityError):
    http_status = 400


class ChargingSessionAlreadyActiveError(FacilityError):
    http_status = 409


class ChargingSessionNotActiveError(FacilityError):
    http_status = 409


class SpotOccupiedError(FacilityError):
    http_status = 409


class InvalidRateError(FacilityError):
    http_status = 400


class ActiveChargingSessionError(FacilityError):
    """Raised when trying to check out a vehicle with an active charging session."""
    http_status = 409
