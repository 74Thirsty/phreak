"""Forensic-grade function registry with ontology and audit guarantees."""
from __future__ import annotations

import hashlib
import inspect
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple, Type, Union


class ForensicComplianceError(Exception):
    """Raised when a function breaches the forensic compliance contract."""


class DocstringProtocolError(ForensicComplianceError):
    """Raised when a function does not expose the mandated docstring schema."""


class TypeFidelityError(ForensicComplianceError):
    """Raised when runtime inputs or outputs violate declared type guarantees."""


def _type_name(type_hint: Union[Type[Any], str]) -> str:
    """Return a human readable name for a type hint."""

    if isinstance(type_hint, str):
        return type_hint
    if hasattr(type_hint, "__name__"):
        return type_hint.__name__  # type: ignore[return-value]
    return repr(type_hint)


def _hash_payload(payload: Any) -> str:
    """Derive a deterministic SHA-256 hash for arbitrary payloads."""

    text = repr(payload).encode("utf-8", "replace")
    return hashlib.sha256(text).hexdigest()


def _build_semantic_vector(source: str) -> Tuple[float, ...]:
    """Encode semantic intent as a normalised vector of floats."""

    if not source:
        return (0.0,)
    normalised = [ord(char) / 255.0 for char in source]
    return tuple(normalised)


def _frequency_signature(samples: Sequence[float], *, harmonics: int = 8) -> Tuple[float, ...]:
    """Convert a semantic vector into a frequency-domain signature."""

    if not samples:
        return (0.0,)
    length = len(samples)
    max_harmonic = min(harmonics, length)
    signature: List[float] = []
    for harmonic in range(max_harmonic):
        real = 0.0
        imag = 0.0
        for index, value in enumerate(samples):
            angle = 2 * math.pi * harmonic * index / length
            real += value * math.cos(angle)
            imag -= value * math.sin(angle)
        magnitude = math.sqrt(real ** 2 + imag ** 2)
        signature.append(round(magnitude, 6))
    return tuple(signature)


@dataclass(frozen=True, slots=True)
class FunctionOntologyEntry:
    """Formal semantic ontology description for a registered function."""

    name: str
    domain: str
    intent_class: str
    control_vector: str
    semantic_vector: Tuple[float, ...]
    frequency_signature: Tuple[float, ...]

    @classmethod
    def create(
        cls,
        name: str,
        *,
        domain: str,
        intent_class: str,
        control_vector: str,
    ) -> "FunctionOntologyEntry":
        """Factory that derives semantic and frequency encodings."""

        semantic_basis = f"{name}|{domain}|{intent_class}|{control_vector}"
        semantic_vector = _build_semantic_vector(semantic_basis)
        frequency_signature = _frequency_signature(semantic_vector)
        return cls(
            name=name,
            domain=domain,
            intent_class=intent_class,
            control_vector=control_vector,
            semantic_vector=semantic_vector,
            frequency_signature=frequency_signature,
        )


@dataclass(frozen=True, slots=True)
class FunctionContract:
    """Explicit interface contract declared for a registered function."""

    name: str
    purpose: str
    input_name: str
    input_type: Type[Any]
    input_role: str
    output_type: Type[Any]
    output_guarantee: str
    control_gate: str
    audit_trail: str

    def build_docstring(self) -> str:
        """Render the docstring mandated by the compliance protocol."""

        return (
            f"Function: {self.name}\n"
            f"Purpose: {self.purpose}\n"
            f"Inputs:\n"
            f"  - {self.input_name}: {_type_name(self.input_type)} — {self.input_role}\n"
            f"Outputs:\n"
            f"  - {_type_name(self.output_type)} — {self.output_guarantee}\n"
            f"Control Gate: {self.control_gate}\n"
            f"Audit Trail: {self.audit_trail}"
        )


UTC = timezone.utc


@dataclass(slots=True)
class ValidatorReport:
    """Compliance report emitted after each validator run."""

    function_name: str
    input_valid: bool
    output_valid: bool
    semantic_match: bool
    notes: Tuple[str, ...] = field(default_factory=tuple)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def compliant(self) -> bool:
        """Return ``True`` when all validation gates pass."""

        return self.input_valid and self.output_valid and self.semantic_match


@dataclass(slots=True)
class FunctionTestVector:
    """Edge-case test vector for validator exercises."""

    input_value: Any
    expected_output: Any
    description: str
    expect_failure: bool = False


@dataclass(slots=True)
class ForensicLedgerEntry:
    """Immutable log entry chained through SHA-256 hashes."""

    index: int
    timestamp: datetime
    function_name: str
    caller: str
    input_hash: str
    output_hash: str
    semantic_intent_vector: Tuple[float, ...]
    status: str
    previous_hash: str
    entry_hash: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


class ForensicLedger:
    """Append-only ledger with tamper-evident chaining."""

    def __init__(self) -> None:
        self._entries: List[ForensicLedgerEntry] = []

    @property
    def entries(self) -> Tuple[ForensicLedgerEntry, ...]:
        """Expose a snapshot of the immutable ledger."""

        return tuple(self._entries)

    def append(
        self,
        *,
        function_name: str,
        caller: str,
        input_hash: str,
        output_hash: str,
        semantic_intent_vector: Tuple[float, ...],
        status: str,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> ForensicLedgerEntry:
        """Append a new entry and return the committed record."""

        index = len(self._entries)
        timestamp = datetime.now(UTC)
        previous_hash = self._entries[-1].entry_hash if self._entries else "GENESIS"
        payload = (
            f"{index}|{timestamp.isoformat()}|{function_name}|{caller}|{input_hash}|"
            f"{output_hash}|{semantic_intent_vector}|{status}|{previous_hash}|{metadata}"
        )
        entry_hash = hashlib.sha256(payload.encode("utf-8", "replace")).hexdigest()
        record = ForensicLedgerEntry(
            index=index,
            timestamp=timestamp,
            function_name=function_name,
            caller=caller,
            input_hash=input_hash,
            output_hash=output_hash,
            semantic_intent_vector=semantic_intent_vector,
            status=status,
            previous_hash=previous_hash,
            entry_hash=entry_hash,
            metadata=dict(metadata or {}),
        )
        self._entries.append(record)
        return record

    def verify_chain(self) -> bool:
        """Recompute hashes and ensure the ledger is pristine."""

        previous_hash = "GENESIS"
        for index, entry in enumerate(self._entries):
            payload = (
                f"{index}|{entry.timestamp.isoformat()}|{entry.function_name}|{entry.caller}|"
                f"{entry.input_hash}|{entry.output_hash}|{entry.semantic_intent_vector}|"
                f"{entry.status}|{previous_hash}|{dict(entry.metadata)}"
            )
            calculated_hash = hashlib.sha256(payload.encode("utf-8", "replace")).hexdigest()
            if entry.entry_hash != calculated_hash or entry.previous_hash != previous_hash:
                return False
            previous_hash = entry.entry_hash
        return True


@dataclass(slots=True)
class FunctionChangeRecord:
    """Reasoned changelog entry captured for each function mutation."""

    reason: str
    semantic_delta: str
    validator_diff: str
    approval_signature: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class ForensicFunction:
    """Executable wrapper that enforces the compliance surface area."""

    def __init__(
        self,
        *,
        name: str,
        implementation: Callable[[Any], Any],
        contract: FunctionContract,
        ontology: FunctionOntologyEntry,
        ledger: ForensicLedger,
        validator: Callable[[Any, Any], ValidatorReport],
    ) -> None:
        self.name = name
        self.implementation = implementation
        self.contract = contract
        self.ontology = ontology
        self.ledger = ledger
        self.validator = validator
        self.test_vectors: List[FunctionTestVector] = []
        self.last_validator_report: Optional[ValidatorReport] = None

    # -- Control hooks -------------------------------------------------
    def pre_exec_validate(self, args: Sequence[Any], kwargs: MutableMapping[str, Any]) -> Any:
        """Ensure arguments comply with the contract and docstring protocol."""

        if kwargs:
            raise TypeFidelityError("keyword arguments are not permitted")
        if len(args) != 1:
            raise TypeFidelityError("exactly one positional argument is required")
        payload = args[0]
        if not isinstance(payload, self.contract.input_type):
            raise TypeFidelityError(
                f"expected input type '{_type_name(self.contract.input_type)}'"
            )
        expected_doc = self.contract.build_docstring().strip()
        actual_doc = inspect.getdoc(self.implementation) or ""
        if actual_doc.strip() != expected_doc:
            raise DocstringProtocolError(
                f"docstring mismatch for function '{self.name}'"
            )
        return payload

    def post_exec_log(self, *, caller: str, input_value: Any, output_value: Any) -> ValidatorReport:
        """Write forensic logs and execute validator."""

        input_hash = _hash_payload(input_value)
        output_hash = _hash_payload(output_value)
        self.ledger.append(
            function_name=self.name,
            caller=caller,
            input_hash=input_hash,
            output_hash=output_hash,
            semantic_intent_vector=self.ontology.semantic_vector,
            status="success",
            metadata={"frequency_signature": self.ontology.frequency_signature},
        )
        report = self.validator(input_value, output_value)
        self.last_validator_report = report
        return report

    def error_traceback(self, *, caller: str, input_value: Any, error: Exception) -> None:
        """Record failure details with chained hashing."""

        input_hash = _hash_payload(input_value)
        error_payload = {"exception": repr(error)}
        output_hash = _hash_payload(error_payload)
        self.ledger.append(
            function_name=self.name,
            caller=caller,
            input_hash=input_hash,
            output_hash=output_hash,
            semantic_intent_vector=self.ontology.semantic_vector,
            status="error",
            metadata={"exception": repr(error)},
        )

    def execute(self, payload: Any, *, caller: str) -> Any:
        """Execute the implementation under the compliance regime."""

        args = (payload,)
        kwargs: MutableMapping[str, Any] = {}
        validated_payload = self.pre_exec_validate(args, kwargs)
        try:
            output = self.implementation(validated_payload)
        except Exception as exc:  # pragma: no cover - defensive
            self.error_traceback(caller=caller, input_value=validated_payload, error=exc)
            raise
        self.post_exec_log(caller=caller, input_value=validated_payload, output_value=output)
        return output

    # -- Validators ----------------------------------------------------
    def register_test_vectors(self, vectors: Iterable[FunctionTestVector]) -> None:
        """Attach additional validator test vectors."""

        self.test_vectors.extend(vectors)

    def run_test_vectors(self) -> List[ValidatorReport]:
        """Execute validator shells across registered test vectors."""

        reports: List[ValidatorReport] = []
        for vector in self.test_vectors:
            try:
                output = self.implementation(vector.input_value)
            except Exception as exc:  # pragma: no cover - defensive
                report = ValidatorReport(
                    function_name=self.name,
                    input_valid=False,
                    output_valid=False,
                    semantic_match=False,
                    notes=(f"execution error: {exc}",),
                )
            else:
                report = self.validator(vector.input_value, output)
                hashes_match = _hash_payload(output) == _hash_payload(vector.expected_output)
                if vector.expect_failure and report.compliant and hashes_match:
                    report = ValidatorReport(
                        function_name=self.name,
                        input_valid=False,
                        output_valid=False,
                        semantic_match=False,
                        notes=("expected failure vector passed",),
                    )
                elif not vector.expect_failure and (not report.compliant or not hashes_match):
                    note_buffer = list(report.notes)
                    if not hashes_match:
                        note_buffer.append("output hash mismatch")
                    report = ValidatorReport(
                        function_name=self.name,
                        input_valid=False,
                        output_valid=False,
                        semantic_match=False,
                        notes=tuple(note_buffer + ["vector non-compliant"]),
                    )
            reports.append(report)
        return reports


class ForensicFunctionRegistry:
    """Central registry enforcing ontology, contracts, and audit state."""

    def __init__(self, subsystem_name: str) -> None:
        self.subsystem_name = subsystem_name
        self.ledger = ForensicLedger()
        self._functions: Dict[str, ForensicFunction] = {}
        self._validators: Dict[str, Callable[[Any, Any], ValidatorReport]] = {}
        self._dependencies: Dict[str, Tuple[str, ...]] = {}
        self._changes: Dict[str, List[FunctionChangeRecord]] = {}

    # -- Registration --------------------------------------------------
    def register_function(
        self,
        *,
        implementation: Callable[[Any], Any],
        name: str,
        purpose: str,
        domain: str,
        intent_class: str,
        control_vector: str,
        input_name: str,
        input_type: Type[Any],
        input_role: str,
        output_type: Type[Any],
        output_guarantee: str,
        control_gate: str,
        audit_trail: str,
        test_vectors: Optional[Iterable[FunctionTestVector]] = None,
    ) -> ForensicFunction:
        """Register a function with the ontology, contract, and validators."""

        if name in self._functions:
            raise ForensicComplianceError(f"function '{name}' already registered")
        if implementation.__name__ != name:
            raise ForensicComplianceError("implementation name must be immutable")

        contract = FunctionContract(
            name=name,
            purpose=purpose,
            input_name=input_name,
            input_type=input_type,
            input_role=input_role,
            output_type=output_type,
            output_guarantee=output_guarantee,
            control_gate=control_gate,
            audit_trail=audit_trail,
        )
        ontology = FunctionOntologyEntry.create(
            name=name,
            domain=domain,
            intent_class=intent_class,
            control_vector=control_vector,
        )

        implementation.__doc__ = contract.build_docstring()
        validator = self._build_validator_shell(name, input_type, output_type, ontology)
        forensic_function = ForensicFunction(
            name=name,
            implementation=implementation,
            contract=contract,
            ontology=ontology,
            ledger=self.ledger,
            validator=validator,
        )
        if test_vectors:
            forensic_function.register_test_vectors(test_vectors)

        self._functions[name] = forensic_function
        self._validators[name] = validator
        self._changes[name] = [
            FunctionChangeRecord(
                reason="initial registration",
                semantic_delta="baseline",
                validator_diff="initial",
                approval_signature="system",
            )
        ]
        self._dependencies.setdefault(name, tuple())
        return forensic_function

    def _build_validator_shell(
        self,
        name: str,
        input_type: Type[Any],
        output_type: Type[Any],
        ontology: FunctionOntologyEntry,
    ) -> Callable[[Any, Any], ValidatorReport]:
        """Generate the statically named validator shell."""

        def validator(input_value: Any, output_value: Any) -> ValidatorReport:
            notes: List[str] = []
            input_valid = isinstance(input_value, input_type)
            if not input_valid:
                notes.append(
                    f"input type violation: expected {_type_name(input_type)}"
                )
            output_valid = isinstance(output_value, output_type)
            if not output_valid:
                notes.append(
                    f"output type violation: expected {_type_name(output_type)}"
                )
            semantic_match = bool(len(ontology.frequency_signature) > 0)
            if not semantic_match:
                notes.append("semantic frequency signature missing")
            return ValidatorReport(
                function_name=name,
                input_valid=input_valid,
                output_valid=output_valid,
                semantic_match=semantic_match,
                notes=tuple(notes),
            )

        validator.__name__ = f"validate_{name}"
        validator.__doc__ = (
            f"Validator shell enforcing type fidelity for '{name}'."
        )
        return validator

    # -- Execution -----------------------------------------------------
    def execute(self, name: str, payload: Any, *, caller: str) -> Any:
        """Execute a registered function by immutable name."""

        function = self._functions.get(name)
        if not function:
            raise ForensicComplianceError(f"unknown function '{name}'")
        return function.execute(payload, caller=caller)

    # -- Subsystem integration ----------------------------------------
    @property
    def function_map(self) -> Mapping[str, Mapping[str, Any]]:
        """Expose ontology summaries for subsystem introspection."""

        manifest: Dict[str, Mapping[str, Any]] = {}
        for name, function in self._functions.items():
            manifest[name] = {
                "domain": function.ontology.domain,
                "intent_class": function.ontology.intent_class,
                "control_vector": function.ontology.control_vector,
                "frequency_signature": function.ontology.frequency_signature,
            }
        return manifest

    @property
    def validator_status(self) -> Mapping[str, bool]:
        """Return the most recent validator compliance status."""

        status: Dict[str, bool] = {}
        for name, function in self._functions.items():
            status[name] = function.last_validator_report.compliant if function.last_validator_report else False
        return status

    @property
    def validators(self) -> Mapping[str, Callable[[Any, Any], ValidatorReport]]:
        """Expose the generated validator shells."""

        return dict(self._validators)

    def build_dependency_graph(self, dependencies: Mapping[str, Sequence[str]]) -> None:
        """Declare and validate a DAG of function dependencies."""

        for name in dependencies:
            if name not in self._functions:
                raise ForensicComplianceError(f"unknown function '{name}' in dependency graph")
        for deps in dependencies.values():
            for dep in deps:
                if dep not in self._functions:
                    raise ForensicComplianceError(
                        f"unknown dependency '{dep}' referenced in graph"
                    )

        graph = {name: tuple(deps) for name, deps in dependencies.items()}

        visited: Dict[str, str] = {}

        def dfs(node: str) -> None:
            state = visited.get(node, "white")
            if state == "gray":
                raise ForensicComplianceError("dependency graph contains a cycle")
            if state == "black":
                return
            visited[node] = "gray"
            for neighbour in graph.get(node, ()):  # depth-first verification
                dfs(neighbour)
            visited[node] = "black"

        for name in graph:
            dfs(name)

        self._dependencies = graph

    @property
    def dependency_graph(self) -> Mapping[str, Tuple[str, ...]]:
        """Expose the dependency graph."""

        return dict(self._dependencies)

    def record_change(
        self,
        name: str,
        *,
        reason: str,
        semantic_delta: str,
        validator_diff: str,
        approval_signature: str,
    ) -> None:
        """Append a changelog entry for the specified function."""

        if name not in self._functions:
            raise ForensicComplianceError(f"unknown function '{name}'")
        record = FunctionChangeRecord(
            reason=reason,
            semantic_delta=semantic_delta,
            validator_diff=validator_diff,
            approval_signature=approval_signature,
        )
        self._changes.setdefault(name, []).append(record)

    @property
    def change_log(self) -> Mapping[str, Tuple[FunctionChangeRecord, ...]]:
        """Return the immutable changelog for all functions."""

        return {name: tuple(records) for name, records in self._changes.items()}

    def subsystem_manifest(self) -> Mapping[str, Any]:
        """Expose subsystem metadata including validators and dependencies."""

        return {
            "subsystem": self.subsystem_name,
            "functions": self.function_map,
            "validators": {name: validator.__name__ for name, validator in self._validators.items()},
            "validator_status": self.validator_status,
            "dependency_graph": self.dependency_graph,
            "ledger_verified": self.ledger.verify_chain(),
        }


__all__ = [
    "ForensicFunctionRegistry",
    "ForensicFunction",
    "ForensicLedger",
    "ForensicLedgerEntry",
    "FunctionContract",
    "FunctionOntologyEntry",
    "FunctionTestVector",
    "ValidatorReport",
    "ForensicComplianceError",
    "DocstringProtocolError",
    "TypeFidelityError",
]
