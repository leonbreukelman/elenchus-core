from __future__ import annotations

from .actions import normalize_action_type
from .models import EvaluationRequest, PolicyFinding


def evaluate_sre_policy(request: EvaluationRequest) -> tuple[float, list[PolicyFinding]]:
    action_type = normalize_action_type(request.proposedAction.type)
    findings: list[PolicyFinding] = []
    score = 0.96
    if request.proposedAction.riskLevel in {"high", "critical"}:
        findings.append(
            PolicyFinding(
                code="high_risk_operator_review_required",
                severity="warning",
                message="High-risk SRE actions require explicit operator review in internal-alpha mode.",
            )
        )
        score -= 0.08
    if action_type in {"delete_data", "drop_database", "force_push"}:
        findings.append(
            PolicyFinding(
                code="irreversible_action_blocker",
                severity="blocker",
                message="Irreversible destructive actions are outside the SRE advisory policy pack.",
            )
        )
        score = 0.2
    if action_type == "page_human":
        score = max(score, 0.98)
    return round(max(0.0, min(1.0, score)), 4), findings
