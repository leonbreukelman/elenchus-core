from __future__ import annotations

from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

EvaluationStatus = Literal["complete", "aborted", "timeout", "error", "skipped"]
EvaluationRecommendation = Literal["proceed", "proceed_with_caveats", "reconsider", "escalate", "abort_signal_only"]
CalibrationState = Literal["uncalibrated_internal_alpha", "calibrated_internal", "calibrated_production"]
DomainName = Literal["sre", "generic", "tech", "cloud", "security", "software", "ai_ml"]
RiskLevel = Literal["low", "medium", "high", "critical"]
GroundingAnchorKind = Literal["numeric", "entity", "metric_state", "mechanism"]
GroundingAnchorStatus = Literal["present", "absent", "contradicted"]
EvidenceMechanicalStatus = Literal[
    "resolved",
    "missing_ref",
    "hash_verified",
    "hash_mismatch",
    "hash_unverifiable",
    "pointer_missing",
    "pointer_unresolved",
    "duplicate_artifact_id",
    "unreferenced_load_bearing_ground",
]
EvidenceSupportStatus = Literal["supported", "unresolved", "advisory_contradiction"]
EvidenceTrustLevel = Literal[
    "self_consistent_artifact_hash",
    "resolved_artifact_refs",
    "weak_context_proxy",
    "missing_or_unresolved_refs",
    "not_available",
]
MethodTrustStructural = Literal["deterministic", "legacy_free_text"]
CounterfactualProbeTrust = Literal["actual_reexecution", "self_report", "not_run"]

MAX_EVIDENCE_ARTIFACTS = 50
MAX_EVIDENCE_ARTIFACT_CHARS = 20_000
MAX_TOTAL_EVIDENCE_CHARS = 200_000


class ElenchusModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class TypedAction(ElenchusModel):
    type: str
    target: str | None = None
    parameters: dict[str, Any] | None = None
    expectedEffect: str | None = None
    riskLevel: RiskLevel | None = None


class EvidenceArtifact(ElenchusModel):
    id: str = Field(min_length=1, max_length=200)
    type: str = Field(min_length=1, max_length=120)
    contentPointer: str | None = Field(default=None, max_length=1000)
    content: str | None = Field(default=None, max_length=MAX_EVIDENCE_ARTIFACT_CHARS)
    sha256: str | None = Field(default=None, min_length=64, max_length=64)
    metadata: dict[str, Any] | None = None


class RationaleGround(ElenchusModel):
    text: str = Field(min_length=1)
    evidenceRefs: list[str] = Field(default_factory=list)
    loadBearing: bool = True


class RejectedAlternativeRationale(ElenchusModel):
    actionId: str | None = None
    action: TypedAction | None = None
    reason: str = Field(min_length=1)
    evidenceRefs: list[str] = Field(default_factory=list)


class StructuredRationale(ElenchusModel):
    claim: str = Field(min_length=1)
    grounds: list[RationaleGround] = Field(default_factory=list)
    warrants: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    rejectedAlternatives: list[RejectedAlternativeRationale] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    wouldChangeIf: list[str] = Field(default_factory=list)


class EvaluationRequest(ElenchusModel):
    traceId: str = Field(min_length=3)
    domain: DomainName
    context: str = Field(min_length=10)
    proposedAction: TypedAction
    rationale: str = Field(min_length=10)
    metadata: dict[str, Any] | None = None
    availableActions: list[TypedAction] | None = None
    structuredRationale: StructuredRationale | None = None
    evidenceBundle: list[EvidenceArtifact] | None = Field(default=None, max_length=MAX_EVIDENCE_ARTIFACTS)
    domainHints: list[DomainName] = Field(default_factory=list)

    @model_validator(mode="after")
    def evidence_bundle_total_content_is_bounded(self) -> Self:
        if self.evidenceBundle is None:
            return self
        total = sum(len(artifact.content or "") for artifact in self.evidenceBundle)
        if total > MAX_TOTAL_EVIDENCE_CHARS:
            raise ValueError(f"evidenceBundle content exceeds {MAX_TOTAL_EVIDENCE_CHARS} characters")
        return self


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


class EvidenceResolutionSummary(ElenchusModel):
    resolved: int = 0
    missingRef: int = 0
    hashVerified: int = 0
    hashMismatch: int = 0
    hashUnverifiable: int = 0
    pointerMissing: int = 0
    pointerUnresolved: int = 0
    duplicateArtifactId: int = 0
    supported: int = 0
    unresolved: int = 0
    advisoryContradiction: int = 0
    loadBearingGrounds: int = 0
    unreferencedLoadBearing: int = 0


class EvidenceRefAssessment(ElenchusModel):
    artifactId: str
    statuses: list[EvidenceMechanicalStatus]
    pointerPresent: bool
    contentPresent: bool
    hashVerified: bool
    notes: list[str]


class EvidenceGroundAssessment(ElenchusModel):
    index: int
    textHash: str
    evidenceRefs: list[str]
    loadBearing: bool
    mechanicalStatuses: list[EvidenceMechanicalStatus]
    supportStatus: EvidenceSupportStatus
    mechanicalScore: float
    supportScore: float
    score: float
    notes: list[str]


class EvidenceResolutionAssessment(ElenchusModel):
    score: float
    mechanicalScore: float
    supportScore: float
    summary: EvidenceResolutionSummary
    refs: list[EvidenceRefAssessment]
    grounds: list[EvidenceGroundAssessment]
    notes: list[str]


class MethodTrust(ElenchusModel):
    structural: MethodTrustStructural
    evidenceResolution: EvidenceTrustLevel
    counterfactualProbe: CounterfactualProbeTrust
    notes: list[str]


def default_method_trust() -> MethodTrust:
    return MethodTrust(
        structural="legacy_free_text",
        evidenceResolution="not_available",
        counterfactualProbe="not_run",
        notes=[
            "Legacy free-text request: no structured evidence-resolution layer was available.",
            "Counterfactual probing was not run; no operational-agent re-execution contract was supplied.",
        ],
    )


class EvaluationSubscores(ElenchusModel):
    rationaleSpecificity: float
    actionCoupling: float
    alternativeResistance: float
    policyAlignment: float
    contextGrounding: float
    evidenceResolution: float | None = None
    evidenceCoverage: float | None = None
    structuralCompleteness: float | None = None


class RubricMetadata(ElenchusModel):
    evaluatorVersion: str
    rubricVersion: str
    calibration: CalibrationState
    signalName: Literal["rationale-action specificity", "task-local evidence-resolving explanation-quality auditor"]
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
    "unresolved_evidence_refs",
    "evidence_hash_mismatch",
    "evidence_hash_unverifiable",
    "duplicate_evidence_artifact_id",
    "counterfactual_probe_not_run",
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
    evidenceResolution: EvidenceResolutionAssessment | None = None
    methodTrust: MethodTrust = Field(default_factory=default_method_trust)
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
