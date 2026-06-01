from __future__ import annotations

from datetime import UTC, datetime

from .grounding import GROUNDING_RULESET_FINGERPRINT, LOW_GROUNDING_THRESHOLD, MEDIUM_GROUNDING_THRESHOLD
from .hash import sha256_hex
from .models import (
    AlternativeAction,
    ContextGroundingAssessment,
    EvaluationRecommendation,
    EvaluationReport,
    EvaluationRequest,
    EvaluationStatus,
    EvaluationSubscores,
    PolicyFinding,
    ProviderMetadata,
    ReadinessMetadata,
    RubricMetadata,
    SupportAssessment,
    SupportMarginReliability,
    ToulminArgument,
)
from .providers import DETERMINISTIC_PROVIDER_METADATA

EVALUATOR_VERSION = "py-v2-alpha-2026-06-01"
PRODUCT_SEMANTICS = (
    "Uncalibrated internal-alpha rationale-action specificity signal with a deterministic context-grounding proxy. "
    "It estimates whether the stated rationale specifically supports the proposed action over typed near-neighbor alternatives "
    "and whether load-bearing rationale anchors are present, absent, or contradicted in the supplied context; it does not validate "
    "objective truth, hidden reasoning, chain-of-thought faithfulness, production readiness, or machine-actionable consumption."
)
OVERALL_WEIGHTS = {
    "rationaleSpecificity": 0.23,
    "actionCoupling": 0.22,
    "alternativeResistance": 0.20,
    "policyAlignment": 0.15,
    "contextGrounding": 0.20,
}
RECOMMENDATION_CAP_ORDER: tuple[EvaluationRecommendation, ...] = (
    "proceed",
    "proceed_with_caveats",
    "reconsider",
    "escalate",
)
EVALUATOR_FINGERPRINT = sha256_hex(
    str({"version": EVALUATOR_VERSION, "weights": OVERALL_WEIGHTS, "grounding": GROUNDING_RULESET_FINGERPRINT})
)[:16]
RUBRIC = RubricMetadata(
    evaluatorVersion=EVALUATOR_VERSION,
    rubricVersion="sre-specificity-py-v0",
    calibration="uncalibrated_internal_alpha",
    signalName="rationale-action specificity",
    evaluatorFingerprint=EVALUATOR_FINGERPRINT,
)


def clamp01(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def overall_signal(subscores: EvaluationSubscores) -> float:
    return clamp01(
        subscores.rationaleSpecificity * OVERALL_WEIGHTS["rationaleSpecificity"]
        + subscores.actionCoupling * OVERALL_WEIGHTS["actionCoupling"]
        + subscores.alternativeResistance * OVERALL_WEIGHTS["alternativeResistance"]
        + subscores.policyAlignment * OVERALL_WEIGHTS["policyAlignment"]
        + subscores.contextGrounding * OVERALL_WEIGHTS["contextGrounding"]
    )


def _base_recommendation(overall: float | None, findings: list[PolicyFinding]) -> EvaluationRecommendation:
    if overall is None:
        return "abort_signal_only"
    if any(finding.severity == "blocker" for finding in findings):
        return "escalate"
    if overall >= 0.75:
        return "proceed"
    if overall >= 0.55:
        return "proceed_with_caveats"
    if overall >= 0.35:
        return "reconsider"
    return "escalate"


def _cap_recommendation(
    recommendation: EvaluationRecommendation, cap: EvaluationRecommendation
) -> EvaluationRecommendation:
    if recommendation not in RECOMMENDATION_CAP_ORDER or cap not in RECOMMENDATION_CAP_ORDER:
        return recommendation
    return (
        cap if RECOMMENDATION_CAP_ORDER.index(recommendation) < RECOMMENDATION_CAP_ORDER.index(cap) else recommendation
    )


def recommend(
    overall: float | None, findings: list[PolicyFinding], grounding: ContextGroundingAssessment | None
) -> EvaluationRecommendation:
    base = _base_recommendation(overall, findings)
    if base in {"abort_signal_only", "escalate"} or any(finding.severity == "blocker" for finding in findings):
        return base
    if grounding is None:
        return base
    if grounding.summary.contradicted > 0:
        return _cap_recommendation(base, "reconsider")
    if grounding.score < LOW_GROUNDING_THRESHOLD:
        return _cap_recommendation(base, "reconsider")
    if grounding.score < MEDIUM_GROUNDING_THRESHOLD:
        return _cap_recommendation(base, "proceed_with_caveats")
    return base


def support_with_margin_reliability(support: SupportAssessment) -> SupportAssessment:
    return support.model_copy(
        update={
            "marginReliability": SupportMarginReliability(
                state="unreliable_internal_alpha",
                reason="non_positive_margin" if support.specificityMargin <= 0 else "benchmark_antiseparation",
                message="specificityMargin is an uncalibrated internal-alpha diagnostic and is currently not reliable as production evidence.",
            )
        }
    )


def top_weaknesses(
    subscores: EvaluationSubscores,
    support: SupportAssessment,
    findings: list[PolicyFinding],
    grounding: ContextGroundingAssessment,
) -> list[str]:
    items: list[str] = []
    if subscores.rationaleSpecificity < 0.55:
        items.append("Rationale lacks concrete thresholds, causal links, or evidence markers.")
    if subscores.actionCoupling < 0.55:
        items.append("Rationale does not strongly couple to the proposed action type.")
    if subscores.contextGrounding < 0.6:
        items.append(
            "Context grounding is weak: load-bearing rationale anchors are absent or contradicted in the supplied context."
        )
    if grounding.summary.contradicted > 0:
        items.append("Context grounding found contradicted load-bearing rationale anchors.")
    if support.specificityMargin < 0.2:
        items.append("Strongest near-neighbor alternative remains similarly supported.")
    items.extend(finding.message for finding in findings if finding.severity != "info")
    return items[:5]


def confidence(
    subscores: EvaluationSubscores, support: SupportAssessment, grounding: ContextGroundingAssessment
) -> float:
    coverage = grounding.summary.present / grounding.summary.loadBearing if grounding.summary.loadBearing else 0.45
    contradiction_penalty = 0.15 if grounding.summary.contradicted > 0 else 0.0
    return clamp01(
        0.2
        + abs(support.specificityMargin) * 0.3
        + subscores.policyAlignment * 0.15
        + subscores.contextGrounding * 0.25
        + coverage * 0.1
        - contradiction_penalty
    )


def readiness(
    status: EvaluationStatus,
    overall: float | None,
    grounding: ContextGroundingAssessment | None,
    findings: list[PolicyFinding],
) -> ReadinessMetadata:
    reasons: list[str] = ["uncalibrated_internal_alpha", "specificity_margin_unreliable"]
    if status != "complete" or overall is None:
        reasons.append("incomplete_evaluation")
    if overall is not None and overall < 0.55:
        reasons.append("low_overall_signal")
    if any(finding.severity == "blocker" for finding in findings):
        reasons.append("policy_blocker")
    if grounding is not None:
        if grounding.summary.loadBearing == 0:
            reasons.append("fallback_grounding")
        if grounding.score < MEDIUM_GROUNDING_THRESHOLD:
            reasons.append("weak_context_grounding")
        if grounding.summary.contradicted > 0:
            reasons.append("contradicted_grounding")
    high_priority = [
        reason for reason in reasons if reason not in {"uncalibrated_internal_alpha", "specificity_margin_unreliable"}
    ]
    return ReadinessMetadata(
        operatingMode="internal_alpha_advisory",
        productionDecisionUse="not_validated_for_allow_deny",
        operatorReviewRequired=True,
        reviewNeeded=bool(high_priority),
        advisorySummary="error_no_numeric_signal"
        if status != "complete" or overall is None
        else "internal_alpha_operator_review_required",
        reviewReasons=list(dict.fromkeys(reasons)),  # type: ignore[arg-type]
        blockedUses=[
            "production_allow_deny",
            "machine_actionable_consumption",
            "hidden_chain_of_thought_faithfulness",
            "objective_truth_validation",
        ],
        evaluatorVersion=EVALUATOR_VERSION,
        evaluatorFingerprint=EVALUATOR_FINGERPRINT,
    )


def build_report(
    request: EvaluationRequest,
    toulmin: ToulminArgument,
    alternatives: list[AlternativeAction],
    support: SupportAssessment,
    subscores: EvaluationSubscores,
    grounding: ContextGroundingAssessment,
    findings: list[PolicyFinding],
    provider_metadata: ProviderMetadata = DETERMINISTIC_PROVIDER_METADATA,
    audit_ref: str | None = None,
) -> EvaluationReport:
    support = support_with_margin_reliability(support)
    overall = overall_signal(subscores)
    return EvaluationReport(
        traceId=request.traceId,
        status="complete",
        recommendation=recommend(overall, findings, grounding),
        calibration="uncalibrated_internal_alpha",
        overallSignal=overall,
        subscores=subscores,
        support=support,
        grounding=grounding,
        toulmin=toulmin,
        alternatives=alternatives,
        policyFindings=findings,
        topWeaknesses=top_weaknesses(subscores, support, findings, grounding),
        confidence=confidence(subscores, support, grounding),
        rubric=RUBRIC,
        providerMetadata=provider_metadata,
        auditRef=audit_ref,
        errors=[],
        productSemantics=PRODUCT_SEMANTICS,
        readiness=readiness("complete", overall, grounding, findings),
        createdAt=_now(),
    )


def build_error_report(
    request: EvaluationRequest, message: str, status: EvaluationStatus = "error"
) -> EvaluationReport:
    return EvaluationReport(
        traceId=request.traceId,
        status=status,
        recommendation="abort_signal_only",
        calibration="uncalibrated_internal_alpha",
        overallSignal=None,
        subscores=None,
        support=None,
        grounding=None,
        toulmin=None,
        alternatives=[],
        policyFindings=[],
        topWeaknesses=["Evaluation did not complete; no numeric signal is available."],
        confidence=None,
        rubric=RUBRIC,
        providerMetadata=DETERMINISTIC_PROVIDER_METADATA,
        auditRef=None,
        errors=[message],
        productSemantics=PRODUCT_SEMANTICS,
        readiness=readiness(status, None, None, []),
        createdAt=_now(),
    )
