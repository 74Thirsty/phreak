from datetime import datetime
from pathlib import Path
import sys

import pytest

SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from phreak_v5.models import DeviceStatus, EnrolledDevice, LocationFix
from phreak_v5.services.enrollment import DeviceRegistry, normalize_phone_number


def test_normalize_phone_number_with_default_country_code():
    assert normalize_phone_number("(555) 010-1234") == "+15550101234"


def test_normalize_phone_number_requires_digits():
    with pytest.raises(ValueError):
        normalize_phone_number("abc")


def test_register_and_locate_device_unique_match():
    registry = DeviceRegistry(telemetry=None)
    device = EnrolledDevice(
        device_id="device-1",
        phone_number="5550109876",
        imei="123456789012345",
        alias="Warehouse Tablet",
        status=DeviceStatus.ONLINE,
        last_known_location=LocationFix(
            latitude=37.7749,
            longitude=-122.4194,
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
        ),
    )

    registry.register_device(device)
    result = registry.locate_device("+1 (555) 010-9876")

    assert result.normalized_phone_number == "+15550109876"
    assert result.has_matches is True
    assert result.is_ambiguous is False
    record = result.matches[0]
    assert record.device_id == "device-1"
    assert record.alias == "Warehouse Tablet"
    assert record.status == DeviceStatus.ONLINE
    assert record.last_known_location.latitude == pytest.approx(37.7749)
    assert record.map_url == "https://maps.google.com/?q=37.7749,-122.4194"


def test_locate_device_multiple_matches_returns_all():
    registry = DeviceRegistry(telemetry=None)
    device_a = EnrolledDevice(device_id="device-A", phone_number="+15550101111")
    device_b = EnrolledDevice(device_id="device-B", phone_number="(555) 010-1111")

    registry.register_device(device_a)
    registry.register_device(device_b)

    result = registry.locate_device("5550101111")

    assert result.is_ambiguous is True
    assert {record.device_id for record in result.matches} == {"device-A", "device-B"}


def test_locate_device_no_match_returns_empty_result():
    registry = DeviceRegistry(telemetry=None)
    result = registry.locate_device("+15550102222")

    assert result.has_matches is False
    assert result.matches == ()
