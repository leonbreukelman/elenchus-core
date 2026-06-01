from __future__ import annotations

from .actions import action_terms, affirmed_term_count, generate_near_neighbor_alternatives
from .audit import FileAuditLogger
from .grounding import assess_context_grounding
from .models import EvaluationReport, EvaluationRequest, EvaluationSubscores
from .policy import evaluate_sre_policy
from .providers import DETERMINISTIC_PROVIDER_METADATA, assess_support
from .report import build_error_report, build_report, clamp01
from .toulmin import extract_toulmin_argument


def action_coupling(request: EvaluationRequest) -> float:
    hits = affirmed_term_count(request.rationale, action_terms(request.proposedAction.type))
    return clamp01(0.35 + hits * 0.18)


def evaluate_request(
    request: EvaluationRequest,
    *,
    provider: str = "deterministic",
    audit_logger: FileAuditLogger | None = None,
) -> EvaluationReport:
    if provider != "deterministic":
        return build_error_report(request, f"unsupported provider for Python port: {provider}")
    try:
        toulmin = extract_toulmin_argument(request.rationale, request.proposedAction)
        alternatives = generate_near_neighbor_alternatives(request)
        support = assess_support(request, alternatives)
        policy_score, policy_findings = evaluate_sre_policy(request) if request.domain == "sre" else (0.7, [])
        grounding = assess_context_grounding(request)
        subscores = EvaluationSubscores(
            rationaleSpecificity=toulmin.specificity.value,
            actionCoupling=action_coupling(request),
            alternativeResistance=clamp01(0.5 + support.specificityMargin / 2),
            policyAlignment=policy_score,
            contextGrounding=grounding.score,
        )
        report = build_report(
            request=request,
            toulmin=toulmin,
            alternatives=alternatives,
            support=support,
            subscores=subscores,
            grounding=grounding,
            findings=policy_findings,
            provider_metadata=DETERMINISTIC_PROVIDER_METADATA,
        )
        if audit_logger is not None:
            audit_ref = audit_logger.write(request, report)
            report = report.model_copy(update={"auditRef": audit_ref})
        return report
    except Exception as exc:  # pragma: no cover - defensive status-safe boundary
        return build_error_report(request, str(exc))
