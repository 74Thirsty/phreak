"""Re-export device enrollment helpers for integration tests."""
from phreak_v5.services.enrollment import DeviceRegistry, normalize_phone_number

__all__ = ["DeviceRegistry", "normalize_phone_number"]
