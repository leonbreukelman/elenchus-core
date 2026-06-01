from __future__ import annotations

from .actions import action_terms, affirmed_term_count, generate_near_neighbor_alternatives
from .audit import FileAuditLogger
from .evidence import assess_evidence_resolution
from .grounding import assess_context_grounding
from .models import EvaluationReport, EvaluationRequest, EvaluationSubscores
from .policy import evaluate_sre_policy
from .providers import DETERMINISTIC_PROVIDER_METADATA, assess_support
from .report import build_error_report, build_report, clamp01
from .toulmin import extract_toulmin_argument


def action_coupling(request: EvaluationRequest) -> float:
    hits = affirmed_term_count(request.rationale, action_terms(request.proposedAction.type))
    return clamp01(0.35 + hits * 0.18)


def structural_completeness(request: EvaluationRequest) -> float | None:
    structured = request.structuredRationale
    if structured is None:
        return None
    points = 0.0
    total = 6.0
    if structured.claim.strip():
        points += 1.0
    if structured.grounds:
        points += 1.0
    if structured.warrants:
        points += 1.0
    if structured.rejectedAlternatives:
        points += 1.0
    if structured.uncertainty:
        points += 1.0
    if structured.wouldChangeIf:
        points += 1.0
    return clamp01(points / total)


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
        evidence_resolution = assess_evidence_resolution(request)
        context_grounding_score = grounding.score
        if evidence_resolution is not None:
            context_grounding_score = clamp01(min(context_grounding_score, evidence_resolution.mechanicalScore))
        subscores = EvaluationSubscores(
            rationaleSpecificity=toulmin.specificity.value,
            actionCoupling=action_coupling(request),
            alternativeResistance=clamp01(0.5 + support.specificityMargin / 2),
            policyAlignment=policy_score,
            contextGrounding=context_grounding_score,
            evidenceResolution=evidence_resolution.score if evidence_resolution is not None else None,
            evidenceCoverage=evidence_resolution.mechanicalScore if evidence_resolution is not None else None,
            structuralCompleteness=structural_completeness(request),
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
            evidence_resolution=evidence_resolution,
        )
        if audit_logger is not None:
            audit_ref = audit_logger.write(request, report)
            report = report.model_copy(update={"auditRef": audit_ref})
        return report
    except Exception as exc:  # pragma: no cover - defensive status-safe boundary
        return build_error_report(request, str(exc))
