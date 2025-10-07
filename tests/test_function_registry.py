import inspect
from datetime import UTC, datetime

import pytest

from phreak_v5.services.function_registry import (
    DocstringProtocolError,
    ForensicFunctionRegistry,
    FunctionTestVector,
    TypeFidelityError,
)


def signal_transform(payload: dict) -> dict:
    return {
        "intent": payload["intent"].upper(),
        "timestamp": datetime.now(UTC).isoformat(),
    }


def test_register_function_enforces_contract_and_logs():
    registry = ForensicFunctionRegistry("compliance-lab")

    registry.register_function(
        implementation=signal_transform,
        name="signal_transform",
        purpose="Normalise signalling packets",
        domain="protocol",
        intent_class="transformation",
        control_vector="user-initiated",
        input_name="payload",
        input_type=dict,
        input_role="Structured signal payload",
        output_type=dict,
        output_guarantee="Returns enriched payload",
        control_gate="Operator approval",
        audit_trail="ledger.chain.signal_transform",
        test_vectors=[
            FunctionTestVector(
                input_value={"intent": "ping"},
                expected_output={"intent": "PING"},
                description="Nominal case",
            ),
            FunctionTestVector(
                input_value={"intent": "drop"},
                expected_output={"intent": "DROP"},
                description="Alternate intent",
            ),
        ],
    )

    doc = inspect.getdoc(signal_transform)
    assert doc is not None
    assert "Function: signal_transform" in doc
    assert "Domain" not in doc  # ensures format remains exact

    output = registry.execute("signal_transform", {"intent": "ping"}, caller="unit-test")
    assert output["intent"] == "PING"

    ledger_entries = registry.ledger.entries
    assert len(ledger_entries) == 1
    entry = ledger_entries[0]
    assert entry.function_name == "signal_transform"
    assert entry.metadata["frequency_signature"] == registry.function_map["signal_transform"][
        "frequency_signature"
    ]
    assert registry.ledger.verify_chain() is True

    report = registry._functions["signal_transform"].last_validator_report
    assert report is not None and report.compliant is True

    validator = registry.validators["signal_transform"]
    assert validator.__name__ == "validate_signal_transform"

    manifest = registry.subsystem_manifest()
    assert manifest["subsystem"] == "compliance-lab"
    assert manifest["validator_status"]["signal_transform"] is True

    reports = registry._functions["signal_transform"].run_test_vectors()
    assert len(reports) == 2

    registry.build_dependency_graph({"signal_transform": ()})
    assert registry.dependency_graph["signal_transform"] == ()

    registry.record_change(
        "signal_transform",
        reason="Updated enrichment fields",
        semantic_delta="Added timestamp",
        validator_diff="No change",
        approval_signature="qa-team",
    )
    assert len(registry.change_log["signal_transform"]) == 2


def test_execute_enforces_type_and_docstring():
    registry = ForensicFunctionRegistry("enforcement")

    registry.register_function(
        implementation=signal_transform,
        name="signal_transform",
        purpose="Normalise signalling packets",
        domain="protocol",
        intent_class="transformation",
        control_vector="user-initiated",
        input_name="payload",
        input_type=dict,
        input_role="Structured signal payload",
        output_type=dict,
        output_guarantee="Returns enriched payload",
        control_gate="Operator approval",
        audit_trail="ledger.chain.signal_transform",
    )

    with pytest.raises(TypeFidelityError):
        registry.execute("signal_transform", ["bad"], caller="unit-test")

    registry._functions["signal_transform"].implementation.__doc__ = "tampered"
    with pytest.raises(DocstringProtocolError):
        registry.execute("signal_transform", {"intent": "ping"}, caller="unit-test")
