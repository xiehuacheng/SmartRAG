from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

RiskLevel = Literal["low", "medium", "high"]


@dataclass
class GuardrailDecision:
    action: str
    risk_level: RiskLevel
    requires_approval: bool
    reason_codes: list[str]
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


def _merge_risk(current: RiskLevel, target: RiskLevel) -> RiskLevel:
    order = {"low": 0, "medium": 1, "high": 2}
    return target if order[target] > order[current] else current


def evaluate_web_risk(
    action: str,
    used_web_search: bool,
    risk_tolerance: str = "medium",
    security_level: str = "internal",
) -> GuardrailDecision:
    reasons: list[str] = []
    risk: RiskLevel = "low"
    write_actions = {"kb_ingest", "kb_update"}

    if action not in write_actions:
        return GuardrailDecision(
            action=action,
            risk_level="low",
            requires_approval=False,
            reason_codes=[],
            message="非写操作，无需审批。",
        )

    if risk_tolerance != "high":
        reasons.append("write_operation_default_gate")
        risk = _merge_risk(risk, "medium")

    if used_web_search:
        reasons.append("web_to_kb_write")
        risk = _merge_risk(risk, "high")

    if security_level == "confidential":
        reasons.append("confidential_write")
        risk = _merge_risk(risk, "high")

    requires_approval = len(reasons) > 0
    if requires_approval:
        message = "检测到高风险或受控写操作，需人工审批后执行。"
    else:
        message = "写操作通过风控校验，可直接执行。"

    return GuardrailDecision(
        action=action,
        risk_level=risk,
        requires_approval=requires_approval,
        reason_codes=reasons,
        message=message,
    )

