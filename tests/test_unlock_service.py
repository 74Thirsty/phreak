from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phreak_v5.services.unlock import (
    IMEIValidationError,
    UnlockCodeBreakdown,
    generate_unlock_code,
    normalize_imei,
)


def test_normalize_imei_accepts_formatted_values():
    normalized = normalize_imei("865-319 070:759855")
    assert normalized == "865319070759855"


def test_normalize_imei_rejects_invalid_characters():
    with pytest.raises(IMEIValidationError):
        normalize_imei("12345ABCDE67890")


def test_generate_unlock_code_returns_breakdown():
    result = generate_unlock_code("865319070759855")
    assert isinstance(result, UnlockCodeBreakdown)
    assert result.code == "UNLOCK62"
    assert result.as_tuple() == ("865319070759855", 6, 2, "UNLOCK")
    assert result.to_dict()["components"]["last_block_checksum"] == 6


def test_generate_unlock_code_rejects_bad_checksum():
    with pytest.raises(IMEIValidationError):
        generate_unlock_code("865319070759854")


def test_normalize_imei_requires_string():
    with pytest.raises(TypeError):
        normalize_imei(865319070759855)  # type: ignore[arg-type]


def test_normalize_imei_requires_value():
    with pytest.raises(IMEIValidationError):
        normalize_imei("   ")
