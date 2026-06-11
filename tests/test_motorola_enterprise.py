import json

import pytest

from phreak_v5.services.motorola_enterprise import (
    EnrollmentPayload,
    MotorolaEnterpriseManager,
)


def test_android_device_policy_payload_contains_enrollment_token():
    payload = json.loads(EnrollmentPayload.from_android_device_policy_token("token-1"))

    assert payload[
        "android.app.extra.PROVISIONING_DEVICE_ADMIN_COMPONENT_NAME"
    ].startswith("com.google.android.apps.work.clouddpc/")
    assert payload["android.app.extra.PROVISIONING_ADMIN_EXTRAS_BUNDLE"][
        "com.google.android.apps.work.clouddpc.EXTRA_ENROLLMENT_TOKEN"
    ] == "token-1"


def test_qr_payload_requires_device_admin_component():
    with pytest.raises(ValueError):
        EnrollmentPayload.validate_qr_json("{}")


def test_writes_enrollment_payload_without_qrencode(tmp_path, monkeypatch):
    monkeypatch.setattr("phreak_v5.services.motorola_enterprise.shutil.which", lambda _: None)
    payload = EnrollmentPayload.from_android_device_policy_token("token-1")

    payload_path, qr_path = MotorolaEnterpriseManager.write_enrollment_artifacts(
        payload, tmp_path
    )

    assert json.loads(payload_path.read_text())[
        "android.app.extra.PROVISIONING_ADMIN_EXTRAS_BUNDLE"
    ]
    assert qr_path is None
