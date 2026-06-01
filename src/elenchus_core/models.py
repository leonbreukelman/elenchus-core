from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

EvaluationStatus = Literal["complete", "aborted", "timeout", "error", "skipped"]
EvaluationRecommendation = Literal["proceed", "proceed_with_caveats", "reconsider", "escalate", "abort_signal_only"]
CalibrationState = Literal["uncalibrated_internal_alpha", "calibrated_internal", "calibrated_production"]
DomainName = Literal["sre", "generic"]
RiskLevel = Literal["low", "medium", "high", "critical"]
GroundingAnchorKind = Literal["numeric", "entity", "metric_state", "mechanism"]
GroundingAnchorStatus = Literal["present", "absent", "contradicted"]


class ElenchusModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class TypedAction(ElenchusModel):
    type: str
    target: str | None = None
    parameters: dict[str, Any] | None = None
    expectedEffect: str | None = None
    riskLevel: RiskLevel | None = None


class EvaluationRequest(ElenchusModel):
    traceId: str = Field(min_length=3)
    domain: DomainName
    context: str = Field(min_length=10)
    proposedAction: TypedAction
    rationale: str = Field(min_length=10)
    metadata: dict[str, Any] | None = None


class SpecificityFeatures(ElenchusModel):
    numericThresholds: int
    causalConnectors: int
    domainTerms: int
    actionTerms: int
    evidenceMarkers: int
    hedgeTerms: int


class LinguisticSpecificityScore(ElenchusModel):
    value: float
    features: SpecificityFeatures
    notes: list[str]


class ToulminArgument(ElenchusModel):
    claim: str
    grounds: list[str]
    warrants: list[str]
    backing: list[str]
    qualifiers: list[str]
    rebuttals: list[str]
    specificity: LinguisticSpecificityScore


class AlternativeAction(ElenchusModel):
    id: str
    action: TypedAction
    rationale: str
    contrastWithOriginal: str
    generationMethod: Literal["deterministic_near_neighbor", "provider"] = "deterministic_near_neighbor"


class SupportMarginReliability(ElenchusModel):
    state: Literal["unreliable_internal_alpha", "calibration_required"]
    reason: Literal["benchmark_antiseparation", "non_positive_margin", "uncalibrated_margin"]
    message: str


class SupportAssessment(ElenchusModel):
    originalSupport: float
    strongestAlternativeSupport: float
    specificityMargin: float
    strongestAlternativeId: str | None
    notes: list[str]
    marginReliability: SupportMarginReliability | None = None


class GroundingAnchor(ElenchusModel):
    id: str
    kind: GroundingAnchorKind
    text: str
    normalizedText: str
    loadBearing: bool
    status: GroundingAnchorStatus
    contextEvidence: str | None
    contradictionEvidence: str | None
    weight: float
    notes: list[str]


class ContextGroundingSummary(ElenchusModel):
    present: int
    absent: int
    contradicted: int
    loadBearing: int


class ContextGroundingAssessment(ElenchusModel):
    score: float
    anchors: list[GroundingAnchor]
    summary: ContextGroundingSummary
    notes: list[str]


class EvaluationSubscores(ElenchusModel):
    rationaleSpecificity: float
    actionCoupling: float
    alternativeResistance: float
    policyAlignment: float
    contextGrounding: float


class RubricMetadata(ElenchusModel):
    evaluatorVersion: str
    rubricVersion: str
    calibration: CalibrationState
    signalName: Literal["rationale-action specificity"]
    evaluatorFingerprint: str | None = None


class ProviderMetadata(ElenchusModel):
    provider: str
    model: str
    roles: dict[str, str]
    deterministic: bool


class PolicyFinding(ElenchusModel):
    code: str
    severity: Literal["info", "warning", "blocker"]
    message: str


EvaluationReviewReason = Literal[
    "uncalibrated_internal_alpha",
    "specificity_margin_unreliable",
    "weak_context_grounding",
    "contradicted_grounding",
    "fallback_grounding",
    "policy_blocker",
    "low_overall_signal",
    "incomplete_evaluation",
]
BlockedEvaluationUse = Literal[
    "production_allow_deny",
    "machine_actionable_consumption",
    "hidden_chain_of_thought_faithfulness",
    "objective_truth_validation",
]


class ReadinessMetadata(ElenchusModel):
    operatingMode: Literal["internal_alpha_advisory"]
    productionDecisionUse: Literal["not_validated_for_allow_deny"]
    operatorReviewRequired: Literal[True]
    reviewNeeded: bool
    advisorySummary: Literal["internal_alpha_operator_review_required", "error_no_numeric_signal"]
    reviewReasons: list[EvaluationReviewReason]
    blockedUses: list[BlockedEvaluationUse]
    evaluatorVersion: str
    evaluatorFingerprint: str


class EvaluationReport(ElenchusModel):
    traceId: str
    status: EvaluationStatus
    recommendation: EvaluationRecommendation
    calibration: CalibrationState
    overallSignal: float | None
    subscores: EvaluationSubscores | None
    support: SupportAssessment | None
    grounding: ContextGroundingAssessment | None
    toulmin: ToulminArgument | None
    alternatives: list[AlternativeAction]
    policyFindings: list[PolicyFinding]
    topWeaknesses: list[str]
    confidence: float | None
    rubric: RubricMetadata
    providerMetadata: ProviderMetadata
    auditRef: str | None
    errors: list[str]
    productSemantics: str
    readiness: ReadinessMetadata
    createdAt: str
