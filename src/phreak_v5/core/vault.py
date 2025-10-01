"""Minimal secret storage for PHREAK v5."""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Sequence

from ..telemetry import TelemetryBus

try:
    from cryptography.fernet import Fernet  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    Fernet = None


@dataclass(slots=True)
class VaultEntry:
    value: str
    tags: Sequence[str]
    created_at: str
    updated_at: str


class _SimpleCipher:
    """Fallback XOR-based cipher (not for production use)."""

    def __init__(self, key: bytes) -> None:
        self._key = key

    def encrypt(self, plaintext: str) -> str:
        data = plaintext.encode("utf-8")
        cipher = bytes(b ^ self._key[i % len(self._key)] for i, b in enumerate(data))
        return base64.urlsafe_b64encode(cipher).decode("ascii")

    def decrypt(self, token: str) -> str:
        data = base64.urlsafe_b64decode(token.encode("ascii"))
        plain = bytes(b ^ self._key[i % len(self._key)] for i, b in enumerate(data))
        return plain.decode("utf-8")


class SecurityVault:
    """Stores secrets with optional encryption and tagging."""

    def __init__(
        self,
        *,
        storage_path: Path,
        master_key: str,
        telemetry: Optional[TelemetryBus] = None,
    ) -> None:
        self.storage_path = storage_path
        self.telemetry = telemetry
        key_bytes = master_key.encode("utf-8")
        if Fernet:
            self._cipher = Fernet(base64.urlsafe_b64encode(key_bytes.ljust(32, b"0")[:32]))
            self._mode = "fernet"
        else:
            self._cipher = _SimpleCipher(key_bytes)
            self._mode = "xor"
        self._entries: Dict[str, VaultEntry] = {}
        self._load()

    def bootstrap(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            self._write()

    def store_secret(self, name: str, value: str, *, tags: Optional[Sequence[str]] = None) -> None:
        now = datetime.utcnow().isoformat()
        encrypted = self._encrypt(value)
        entry = VaultEntry(
            value=encrypted,
            tags=tuple(tags or ()),
            created_at=now,
            updated_at=now,
        )
        self._entries[name] = entry
        self._write()
        self._emit("vault.secret_stored", {"name": name, "tags": list(entry.tags)})

    def retrieve_secret(self, name: str) -> Optional[str]:
        entry = self._entries.get(name)
        if not entry:
            return None
        self._emit("vault.secret_accessed", {"name": name})
        return self._decrypt(entry.value)

    def delete_secret(self, name: str) -> bool:
        if name in self._entries:
            del self._entries[name]
            self._write()
            self._emit("vault.secret_deleted", {"name": name})
            return True
        return False

    def list_secrets(self, *, include_tags: bool = False) -> Dict[str, Sequence[str]]:
        if include_tags:
            return {name: entry.tags for name, entry in self._entries.items()}
        return {name: () for name in self._entries}

    def _encrypt(self, value: str) -> str:
        if Fernet and self._mode == "fernet":
            return self._cipher.encrypt(value.encode("utf-8")).decode("ascii")  # type: ignore[no-any-return]
        return self._cipher.encrypt(value)  # type: ignore[no-any-return]

    def _decrypt(self, token: str) -> str:
        if Fernet and self._mode == "fernet":
            return self._cipher.decrypt(token.encode("ascii")).decode("utf-8")  # type: ignore[no-any-return]
        return self._cipher.decrypt(token)  # type: ignore[no-any-return]

    def _emit(self, topic: str, payload: dict) -> None:
        if self.telemetry:
            self.telemetry.emit(topic, payload)

    def _load(self) -> None:
        if not self.storage_path.exists():
            return
        try:
            data = json.loads(self.storage_path.read_text())
            self._entries = {
                name: VaultEntry(
                    value=entry["value"],
                    tags=tuple(entry.get("tags", ())),
                    created_at=entry.get("created_at", datetime.utcnow().isoformat()),
                    updated_at=entry.get("updated_at", datetime.utcnow().isoformat()),
                )
                for name, entry in data.items()
            }
        except json.JSONDecodeError:
            self._entries = {}

    def _write(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            name: {
                "value": entry.value,
                "tags": list(entry.tags),
                "created_at": entry.created_at,
                "updated_at": entry.updated_at,
            }
            for name, entry in self._entries.items()
        }
        self.storage_path.write_text(json.dumps(data, indent=2, sort_keys=True))


__all__ = ["SecurityVault", "VaultEntry"]
