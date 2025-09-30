"""Device enrollment and lookup helpers for PHREAK v5."""
from __future__ import annotations

import re
from dataclasses import replace
from typing import Dict, Optional, Set, Tuple

from ..models import (
    DeviceLookupResult,
    DeviceLocationRecord,
    DeviceStatus,
    EnrolledDevice,
    LocationFix,
)

try:
    from ..telemetry import TelemetryBus
except ImportError:  # pragma: no cover - helpful during static analysis
    TelemetryBus = None  # type: ignore

E164_PATTERN = re.compile(r"^\+[1-9]\d{1,14}$")


def normalize_phone_number(phone_number: str, default_country_code: str = "+1") -> str:
    """Normalise phone numbers into the E.164 format."""

    if not phone_number:
        raise ValueError("phone_number is required")

    stripped = phone_number.strip()
    digits = re.sub(r"\D", "", stripped)

    if stripped.startswith("+"):
        normalized = "+" + digits
    else:
        if not default_country_code:
            raise ValueError("default_country_code is required for local numbers")
        country = re.sub(r"\D", "", default_country_code)
        if not country:
            raise ValueError("default_country_code must contain digits")
        normalized = f"+{country}{digits}"

    if not E164_PATTERN.match(normalized):
        raise ValueError(f"invalid phone number format: {phone_number}")

    return normalized


class DeviceRegistry:
    """Stores metadata for enrolled devices and resolves phone lookups."""

    def __init__(
        self,
        *,
        telemetry: Optional["TelemetryBus"] = None,
        default_country_code: str = "+1",
    ) -> None:
        self.telemetry = telemetry
        self.default_country_code = default_country_code
        self._devices: Dict[str, EnrolledDevice] = {}
        self._phone_index: Dict[str, Set[str]] = {}

    # -- Registration -------------------------------------------------
    def register_device(self, device: EnrolledDevice) -> EnrolledDevice:
        normalized_phone = normalize_phone_number(
            device.phone_number, self.default_country_code
        )
        stored = replace(device, phone_number=normalized_phone)

        existing = self._devices.get(stored.device_id)
        if existing:
            self._remove_phone_index(existing.phone_number, existing.device_id)

        self._devices[stored.device_id] = stored
        self._phone_index.setdefault(normalized_phone, set()).add(stored.device_id)
        self._emit(
            "device_registry.registered",
            {
                "device_id": stored.device_id,
                "phone_number": stored.phone_number,
                "status": stored.status.value,
            },
        )
        return stored

    def unregister_device(self, device_id: str) -> None:
        device = self._devices.pop(device_id, None)
        if not device:
            return
        self._remove_phone_index(device.phone_number, device_id)
        self._emit("device_registry.unregistered", {"device_id": device_id})

    # -- Updates ------------------------------------------------------
    def update_status(self, device_id: str, status: DeviceStatus) -> None:
        device = self._get_required_device(device_id)
        device.update_status(status)
        self._emit(
            "device_registry.status_updated",
            {"device_id": device_id, "status": status.value},
        )

    def update_location(self, device_id: str, location: LocationFix) -> None:
        device = self._get_required_device(device_id)
        device.update_location(location)
        self._emit(
            "device_registry.location_updated",
            {
                "device_id": device_id,
                "phone_number": device.phone_number,
                "latitude": location.latitude,
                "longitude": location.longitude,
                "timestamp": location.timestamp.isoformat(),
            },
        )

    def update_alias(self, device_id: str, alias: Optional[str]) -> None:
        device = self._get_required_device(device_id)
        device.alias = alias
        self._emit(
            "device_registry.alias_updated",
            {"device_id": device_id, "alias": alias or ""},
        )

    # -- Lookup -------------------------------------------------------
    def get_device(self, device_id: str) -> Optional[EnrolledDevice]:
        return self._devices.get(device_id)

    def lookup_by_phone(self, phone_number: str) -> Tuple[EnrolledDevice, ...]:
        normalized = normalize_phone_number(phone_number, self.default_country_code)
        device_ids = self._phone_index.get(normalized, set())
        return tuple(self._devices[device_id] for device_id in device_ids)

    def locate_device(self, phone_number: str) -> DeviceLookupResult:
        normalized = normalize_phone_number(phone_number, self.default_country_code)
        device_ids = self._phone_index.get(normalized, set())

        matches = tuple(
            DeviceLocationRecord(
                device_id=self._devices[device_id].device_id,
                alias=self._devices[device_id].alias,
                status=self._devices[device_id].status,
                last_known_location=self._devices[device_id].last_known_location,
            )
            for device_id in sorted(device_ids)
        )

        topic = "device_registry.lookup.miss"
        if matches:
            topic = (
                "device_registry.lookup.ambiguous"
                if len(matches) > 1
                else "device_registry.lookup.hit"
            )
        self._emit(
            topic,
            {
                "query": phone_number,
                "normalized": normalized,
                "matches": [record.device_id for record in matches],
            },
        )

        return DeviceLookupResult(
            query=phone_number,
            normalized_phone_number=normalized,
            matches=matches,
        )

    # -- Internal -----------------------------------------------------
    def _remove_phone_index(self, phone_number: str, device_id: str) -> None:
        device_ids = self._phone_index.get(phone_number)
        if not device_ids:
            return
        device_ids.discard(device_id)
        if not device_ids:
            self._phone_index.pop(phone_number, None)

    def _get_required_device(self, device_id: str) -> EnrolledDevice:
        device = self._devices.get(device_id)
        if not device:
            raise KeyError(f"device '{device_id}' is not registered")
        return device

    def _emit(self, topic: str, payload: dict) -> None:
        if not self.telemetry:
            return
        try:
            self.telemetry.emit(topic, payload)
        except RuntimeError:
            # If no event loop is running (e.g. unit tests), suppress telemetry errors.
            pass


__all__ = ["DeviceRegistry", "normalize_phone_number"]

