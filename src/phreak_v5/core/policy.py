"""Policy evaluation for PHREAK v5."""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from ..models import PolicyContext, PolicyDecision, PolicyRule
from ..telemetry import TelemetryBus

SAFE_GLOBALS = {"len": len, "any": any, "all": all, "set": set}


class UnsafeExpressionError(ValueError):
    """Raised when a policy expression contains unsupported constructs."""


class _PolicyExpressionValidator(ast.NodeVisitor):
    allowed_nodes = {
        ast.Expression,
        ast.BoolOp,
        ast.BinOp,
        ast.UnaryOp,
        ast.IfExp,
        ast.Compare,
        ast.Call,
        ast.Name,
        ast.Load,
        ast.Constant,
        ast.List,
        ast.Tuple,
        ast.Dict,
        ast.Subscript,
        ast.Slice,
        ast.Index,
        ast.Attribute,
        ast.And,
        ast.Or,
        ast.Not,
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
        ast.In,
        ast.NotIn,
        ast.Is,
        ast.IsNot,
    }

    allowed_calls = {"len", "any", "all", "set"}

    def visit(self, node: ast.AST) -> None:  # type: ignore[override]
        if type(node) not in self.allowed_nodes:
            raise UnsafeExpressionError(f"Unsupported expression: {ast.dump(node)}")
        return super().visit(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        if not isinstance(node.func, ast.Name) or node.func.id not in self.allowed_calls:
            raise UnsafeExpressionError(f"Function {ast.dump(node.func)} not permitted")
        self.generic_visit(node)


@dataclass(slots=True)
class PolicyEvaluation:
    rule: PolicyRule
    matched: bool


class PolicyEngine:
    """Evaluates policy rules before command execution."""

    def __init__(
        self,
        *,
        policy_rules: Sequence[PolicyRule],
        telemetry: TelemetryBus,
    ) -> None:
        self.telemetry = telemetry
        self.rules: List[PolicyRule] = list(policy_rules)

    def add_rule(self, rule: PolicyRule) -> None:
        self.rules.append(rule)

    def evaluate(self, context: PolicyContext, *, extra: Optional[Dict[str, object]] = None) -> PolicyDecision:
        env: Dict[str, object] = {
            "device_ids": tuple(context.device_ids),
            "action": context.action,
            "requested_by": context.requested_by,
            "arguments": dict(context.arguments),
        }
        if extra:
            env.update(extra)

        denies: List[str] = []
        matched_rules: List[PolicyEvaluation] = []

        for rule in self.rules:
            if not rule.condition:
                continue
            try:
                matched = self._evaluate_condition(rule.condition, env)
            except UnsafeExpressionError as exc:
                denies.append(f"Rule {rule.name} invalid: {exc}")
                matched = False
            matched_rules.append(PolicyEvaluation(rule, matched))
            if matched and rule.effect.lower() == "deny":
                denies.append(rule.description or rule.name)

        if denies:
            decision = PolicyDecision.deny(denies)
        else:
            decision = PolicyDecision.allow()

        self.telemetry.emit(
            "policy.evaluated",
            {
                "action": context.action,
                "requested_by": context.requested_by,
                "allowed": decision.allowed,
                "denies": list(decision.reasons),
                "matched_rules": [
                    {
                        "name": eval_result.rule.name,
                        "matched": eval_result.matched,
                        "effect": eval_result.rule.effect,
                    }
                    for eval_result in matched_rules
                ],
            },
        )
        return decision

    def _evaluate_condition(self, condition: str, env: Dict[str, object]) -> bool:
        tree = ast.parse(condition, mode="eval")
        _PolicyExpressionValidator().visit(tree)
        compiled = compile(tree, "<policy>", "eval")
        return bool(eval(compiled, {"__builtins__": SAFE_GLOBALS}, env))


__all__ = ["PolicyEngine", "PolicyRule", "PolicyDecision"]
