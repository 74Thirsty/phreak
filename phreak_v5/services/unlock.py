"""Carrier unlock helper utilities.

This module intentionally implements a *demonstration* unlock-code generator
that mirrors the educational flow shared with the operator console. The real
world algorithms used by OEMs and carriers remain proprietary; however, the
module provides production-quality validation, sanitisation, and
instrumentation so that integrators can experiment with safe mock data.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

__all__ = [
    "IMEIValidationError",
    "UnlockCodeBreakdown",
    "generate_unlock_code",
    "normalize_imei",
]


class IMEIValidationError(ValueError):
    """Raised when a candidate IMEI fails structural validation."""


_ALLOWED_SEPARATORS = {" ", "-", ":"}
_UNLOCK_PREFIX = "UNLOCK"


@dataclass(frozen=True)
class UnlockCodeBreakdown:
    """Structured representation of a generated unlock code.

    Attributes
    ----------
    normalized_imei:
        The sanitised IMEI that passed all validation checks.
    last_block_checksum:
        Checksum derived from the last eight digits of the IMEI.
    first_block_checksum:
        Checksum derived from the first seven digits of the IMEI.
    prefix:
        Prefix applied to the final unlock code. Defaults to ``"UNLOCK"`` but
        is exposed for clarity and future configurability.
    """

    normalized_imei: str
    last_block_checksum: int
    first_block_checksum: int
    prefix: str = _UNLOCK_PREFIX

    @property
    def code(self) -> str:
        """Return the printable unlock code."""

        return f"{self.prefix}{self.last_block_checksum}{self.first_block_checksum}"

    def as_tuple(self) -> Tuple[str, int, int, str]:
        """Expose the breakdown in tuple form for logging/telemetry."""

        return (
            self.normalized_imei,
            self.last_block_checksum,
            self.first_block_checksum,
            self.prefix,
        )

    def to_dict(self) -> dict:
        """Serialise the breakdown for JSON responses."""

        return {
            "imei": self.normalized_imei,
            "code": self.code,
            "components": {
                "prefix": self.prefix,
                "last_block_checksum": self.last_block_checksum,
                "first_block_checksum": self.first_block_checksum,
            },
        }


def normalize_imei(raw_imei: str) -> str:
    """Strip formatting characters and validate allowable IMEI content.

    Parameters
    ----------
    raw_imei:
        The IMEI candidate supplied by a user interface or API.  The function
        accepts digits optionally interspersed with spaces, hyphens, or colons
        as seen on some shipping labels.

    Returns
    -------
    str
        A 15-digit IMEI string.

    Raises
    ------
    TypeError
        If *raw_imei* is not a string.
    IMEIValidationError
        If the IMEI contains illegal characters or an unexpected number of
        digits.
    """

    if not isinstance(raw_imei, str):
        raise TypeError("IMEI must be provided as a string")

    stripped = raw_imei.strip()
    if not stripped:
        raise IMEIValidationError("IMEI is required")

    digits = []
    for char in stripped:
        if char.isdigit():
            digits.append(char)
        elif char in _ALLOWED_SEPARATORS:
            continue
        else:
            raise IMEIValidationError(f"IMEI contains invalid character: '{char}'")

    normalized = "".join(digits)

    if len(normalized) != 15:
        raise IMEIValidationError(
            f"IMEI must contain exactly 15 digits; received {len(normalized)}"
        )

    return normalized


def generate_unlock_code(raw_imei: str) -> UnlockCodeBreakdown:
    """Generate a demonstration unlock code for a validated IMEI.

    The implementation mirrors the educational flow documented in PHREAK's
    network unlock assistant:  we inspect the last eight and first seven digits
    separately, sum each block, reduce it modulo ten, and combine the results
    with the ``UNLOCK`` prefix.

    Parameters
    ----------
    raw_imei:
        IMEI provided by the operator.  Formatting characters such as spaces or
        hyphens are ignored.

    Returns
    -------
    UnlockCodeBreakdown
        Structured information about the generated unlock code.

    Raises
    ------
    IMEIValidationError
        If the IMEI fails structural or checksum validation.
    """

    normalized = normalize_imei(raw_imei)

    if not _is_valid_luhn(normalized):
        raise IMEIValidationError("IMEI failed Luhn checksum validation")

    last_eight = normalized[-8:]
    first_seven = normalized[:7]

    last_checksum = _digit_modulo_sum(last_eight)
    first_checksum = _digit_modulo_sum(first_seven)

    return UnlockCodeBreakdown(
        normalized_imei=normalized,
        last_block_checksum=last_checksum,
        first_block_checksum=first_checksum,
    )


def _digit_modulo_sum(block: str) -> int:
    total = sum(int(digit) for digit in block)
    return total % 10


def _is_valid_luhn(imei: str) -> bool:
    return _luhn_checksum(imei) == 0


def _luhn_checksum(imei: str) -> int:
    digits = [int(char) for char in imei]
    checksum = 0

    # The IMEI Luhn algorithm doubles every second digit from the right (indexing
    # from one).  When the doubled value exceeds nine we sum its digits, which is
    # equivalent to subtracting nine.
    for index, digit in enumerate(reversed(digits), start=1):
        if index % 2 == 0:
            doubled = digit * 2
            if doubled > 9:
                doubled -= 9
            checksum += doubled
        else:
            checksum += digit

    return checksum % 10
