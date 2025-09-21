"""Heuristic ML diagnostics placeholder for PHREAK v5."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from ..telemetry import TelemetryBus


@dataclass(slots=True)
class DiagnosticResult:
    label: str
    confidence: float
    explanation: str


class MLDiagnostics:
    """Applies heuristic classifiers to telemetry and logs."""

    def __init__(self, *, telemetry: TelemetryBus) -> None:
        self.telemetry = telemetry
        self._rules: List[Tuple[str, float, str]] = [
            ("bootloop", 0.7, "Detected repeated boot animation log entries"),
            ("modem_crash", 0.8, "Modem subsystem crash keywords present"),
            ("storage_fault", 0.6, "I/O errors observed in dmesg output"),
        ]

    def analyze_log(self, log_text: str) -> DiagnosticResult:
        lowered = log_text.lower()
        for label, base_conf, explanation in self._rules:
            if label.replace("_", " ") in lowered or label in lowered:
                result = DiagnosticResult(label=label, confidence=base_conf + 0.1, explanation=explanation)
                self.telemetry.emit(
                    "ml.diagnostic",
                    {
                        "label": result.label,
                        "confidence": result.confidence,
                    },
                )
                return result
        result = DiagnosticResult(label="unknown", confidence=0.2, explanation="No heuristics matched")
        self.telemetry.emit("ml.diagnostic", {"label": result.label, "confidence": result.confidence})
        return result


__all__ = ["MLDiagnostics", "DiagnosticResult"]
