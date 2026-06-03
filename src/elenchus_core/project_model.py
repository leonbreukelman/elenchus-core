from __future__ import annotations

import re
from collections import defaultdict
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .models import (
    EvaluationRequest,
    ProjectModelAlignment,
    ProjectModelComponentAlignment,
    ProjectModelFinding,
    ProjectModelNearNeighborResistance,
    ProjectModelScalarAlignment,
    ProjectModelValidity,
)
from .report import clamp01

PROJECT_MODEL_V0_SCHEMA_VERSION = "project-model/v0"

FindingSeverity = Literal["error", "warning"]
Identifier = Annotated[str, Field(min_length=1, pattern=r"^[a-z][a-z0-9_\-]*$")]
NonEmptyString = Annotated[str, Field(min_length=1)]
RiskLevel = Literal["low", "medium", "high"]
ComponentKind = Literal[
    "source",
    "test",
    "documentation",
    "configuration",
    "spec",
    "process",
    "architecture",
    "strategy",
    "data",
    "integration",
    "operations",
    "fixture",
    "unknown",
]
DependencyKind = Literal["requires", "precedes", "blocks", "feeds", "informs"]
ObservableCheckMode = Literal[
    "test",
    "static-analysis",
    "simulation",
    "inspection",
    "artifact-audit",
    "stakeholder-decision",
    "non-code-rubric",
    "external-observation",
]
ProbeType = Literal[
    "held-out-example",
    "counterexample",
    "perturbation",
    "tabletop",
    "negative-control",
]
AssumptionStatus = Literal["assumed", "confirmed", "disputed"]

_DIRECTIONAL_DEPENDENCY_KINDS = {"precedes", "requires", "blocks"}
_VAGUE_IDS = {
    "all",
    "everything",
    "general",
    "misc",
    "miscellaneous",
    "other",
    "project",
    "stuff",
    "tbd",
}
_VAGUE_PHRASES = (
    "and so on",
    "do things",
    "do the work",
    "etc",
    "handle stuff",
    "make better",
    "misc",
    "stuff",
    "things",
    "various",
)
_VAGUE_SURFACES = {"all", "everything", "project", "repo", "repository", "stuff"}
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "before",
    "by",
    "can",
    "do",
    "for",
    "from",
    "has",
    "in",
    "is",
    "it",
    "not",
    "of",
    "or",
    "rather",
    "than",
    "that",
    "the",
    "this",
    "to",
    "when",
    "with",
    "without",
}
_DECORATIVE_TERMS = {
    "best",
    "better",
    "excellent",
    "good",
    "great",
    "improve",
    "improvement",
    "robust",
    "strategic",
    "strong",
}
_NEGATION_WINDOWS = (
    "rather than {term}",
    "instead of {term}",
    "without {term}",
    "not {term}",
    "no {term}",
    "reject {term}",
    "skip {term}",
)
_ADVISORY_NOTE = (
    "Project Model v0 alignment is an advisory deterministic signal; it is not objective truth, "
    "an action-correctness judgment, hidden chain-of-thought detection, or a production allow/deny gate."
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _reject_explicit_nulls(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for key, value in data.items():
                if value is None:
                    raise ValueError(f"{key} must be omitted rather than set to null")
        return data


class Source(_StrictModel):
    task: NonEmptyString
    primaryBacklogItem: NonEmptyString
    repo: NonEmptyString | None = None
    issue: NonEmptyString | None = None


class Component(_StrictModel):
    id: Identifier
    name: NonEmptyString
    kind: ComponentKind
    riskLevel: RiskLevel
    responsibilities: list[NonEmptyString] = Field(min_length=1)
    ownedSurfaces: list[NonEmptyString] = Field(min_length=1)
    observableCheckIds: list[Identifier]


class Dependency(_StrictModel):
    id: Identifier
    fromComponent: Identifier
    toComponent: Identifier
    kind: DependencyKind
    description: NonEmptyString
    observableCheckIds: list[Identifier] = Field(default_factory=list)


class Invariant(_StrictModel):
    id: Identifier
    description: NonEmptyString
    componentIds: list[Identifier]
    observableCheckIds: list[Identifier]


class ObservableCheck(_StrictModel):
    id: Identifier
    componentId: Identifier
    mode: ObservableCheckMode
    description: NonEmptyString
    observableSignal: NonEmptyString
    evidenceRequired: list[NonEmptyString]
    noLiveApi: bool | None = None


class EvidenceRequirement(_StrictModel):
    id: Identifier
    description: NonEmptyString
    acceptedArtifactTypes: list[NonEmptyString] = Field(min_length=1)
    requiredFor: list[Identifier]


class Assumption(_StrictModel):
    id: Identifier
    description: NonEmptyString
    status: AssumptionStatus | None = None


class Risk(_StrictModel):
    id: Identifier
    level: RiskLevel
    description: NonEmptyString
    componentId: Identifier | None = None
    mitigation: NonEmptyString | None = None


class NearNeighborAlternative(_StrictModel):
    id: Identifier
    description: NonEmptyString
    whyNotPrimary: NonEmptyString
    distinguishingEvidence: list[NonEmptyString]


class HeldOutProbe(_StrictModel):
    id: Identifier
    componentId: Identifier
    probeType: ProbeType
    scenario: NonEmptyString
    expectedBehavior: NonEmptyString
    evidenceRequired: list[NonEmptyString]


class VerificationGap(_StrictModel):
    id: Identifier
    severity: RiskLevel
    description: NonEmptyString
    affectedComponentIds: list[Identifier]
    proposedClosureCheck: NonEmptyString


class UnclassifiedProjectSurface(_StrictModel):
    id: Identifier
    description: NonEmptyString
    reasonUnclassified: NonEmptyString
    candidateOwners: list[Identifier]


class AdvisorySignalHandoff(_StrictModel):
    consumer: Literal["elenchus-core"]
    expectedFields: list[NonEmptyString] = Field(min_length=6)
    optionalFLabelHint: bool


class ProjectModelV0(_StrictModel):
    schemaVersion: Literal["project-model/v0"]
    id: Identifier
    source: Source
    goal: NonEmptyString
    nonGoals: list[NonEmptyString]
    components: list[Component] = Field(min_length=1)
    dependencies: list[Dependency]
    invariants: list[Invariant]
    observableChecks: list[ObservableCheck] = Field(min_length=1)
    evidenceRequirements: list[EvidenceRequirement]
    assumptions: list[Assumption]
    risks: list[Risk]
    nearNeighborAlternatives: list[NearNeighborAlternative]
    heldOutProbes: list[HeldOutProbe]
    verificationGaps: list[VerificationGap]
    unclassifiedProjectSurface: list[UnclassifiedProjectSurface]
    advisorySignalHandoff: AdvisorySignalHandoff


class QualityGateFinding(_StrictModel):
    code: str
    severity: FindingSeverity
    location: str
    message: str


class QualityGateReport(_StrictModel):
    passed: bool
    findings: list[QualityGateFinding] = Field(default_factory=list)


def assess_project_model_alignment(request: EvaluationRequest) -> ProjectModelAlignment:
    if request.projectModel is None:
        return _absent_alignment()
    if not isinstance(request.projectModel, dict):
        return _invalid_alignment(
            schema_version=None,
            findings=[
                ProjectModelFinding(
                    code="project_model_not_object",
                    severity="error",
                    location="projectModel",
                    message="Project Model v0 must be supplied as a JSON object.",
                )
            ],
        )

    raw_model = request.projectModel
    quality_report = evaluate_quality_gate(raw_model)
    schema_version = raw_model.get("schemaVersion")
    status: Literal["invalid", "unsupported_version"] = (
        "unsupported_version" if schema_version != PROJECT_MODEL_V0_SCHEMA_VERSION else "invalid"
    )
    if not quality_report.passed:
        return _invalid_alignment(
            schema_version=str(schema_version) if schema_version is not None else None,
            findings=[_finding_from_quality(finding) for finding in quality_report.findings],
            status=status,
        )

    model = ProjectModelV0.model_validate(raw_model)
    rationale_text = _request_rationale_text(request)
    evidence_text = _evidence_text(request)
    context_text = _normalize(" ".join([request.context, evidence_text]))
    component_alignment = _component_alignment(model, request, rationale_text)
    goal_alignment = _goal_alignment(model, rationale_text, component_alignment)
    invariant_violations = _invariant_violations(model, rationale_text, component_alignment)
    dependency_violations = _dependency_violations(model, rationale_text, component_alignment)
    unsupported_assumptions = _unsupported_assumptions(model, rationale_text, context_text)
    evidence_gaps = _evidence_grounding_gaps(model, rationale_text, evidence_text, component_alignment)
    near_neighbor_resistance = _near_neighbor_resistance(model, request, rationale_text)
    held_out_failures = _held_out_probe_failures(model, rationale_text, evidence_text, component_alignment)
    hint, reason = _failure_mode_hint(
        rationale_text=rationale_text,
        component_alignment=component_alignment,
        goal_alignment=goal_alignment,
        invariant_violations=invariant_violations,
        dependency_violations=dependency_violations,
        evidence_gaps=evidence_gaps,
        held_out_failures=held_out_failures,
    )
    return ProjectModelAlignment(
        projectModelPresence="present",
        projectModelValidity=ProjectModelValidity(
            status="valid",
            schemaVersion=model.schemaVersion,
            qualityGatePassed=True,
            findings=[],
        ),
        goalAlignment=goal_alignment,
        componentAlignment=component_alignment,
        invariantViolations=invariant_violations,
        dependencyViolations=dependency_violations,
        unsupportedAssumptions=unsupported_assumptions,
        evidenceGroundingGaps=evidence_gaps,
        nearNeighborResistance=near_neighbor_resistance,
        heldOutProbeFailures=held_out_failures,
        failureModeHint=hint,
        failureModeHintReason=reason,
        notes=[_ADVISORY_NOTE],
    )


def evaluate_quality_gate(model: BaseModel | dict[str, Any]) -> QualityGateReport:
    """Evaluate Project Model v0 structural quality without judging correctness."""

    if isinstance(model, BaseModel):
        model = model.model_dump(mode="json", exclude_none=isinstance(model, ProjectModelV0))
    if not isinstance(model, dict):
        return QualityGateReport(
            passed=False,
            findings=[
                QualityGateFinding(
                    code="schema_validation_error",
                    severity="error",
                    location="<root>",
                    message="Project Model v0 must be a JSON object.",
                )
            ],
        )
    try:
        ProjectModelV0.model_validate(model)
    except ValidationError as exc:
        validation_errors: list[Any] = exc.errors()
    else:
        validation_errors = []

    findings: list[QualityGateFinding] = [
        QualityGateFinding(
            code="schema_validation_error",
            severity="error",
            location=".".join(str(part) for part in error.get("loc", ())) or "<root>",
            message=str(error.get("msg", "Project Model v0 schema validation failed.")),
        )
        for error in validation_errors
    ]

    if model.get("schemaVersion") != PROJECT_MODEL_V0_SCHEMA_VERSION:
        findings.append(
            QualityGateFinding(
                code="unsupported_schema_version",
                severity="error",
                location="schemaVersion",
                message="Project Model quality gate only accepts project-model/v0.",
            )
        )

    components = _list_of_dicts(model.get("components"))
    component_ids = [str(component.get("id", "")) for component in components]
    component_id_set = {component_id for component_id in component_ids if component_id}
    if not components:
        findings.append(
            QualityGateFinding(
                code="missing_components",
                severity="error",
                location="components",
                message="Project Model v0 requires at least one component.",
            )
        )

    observable_checks = _list_of_dicts(model.get("observableChecks"))
    if not observable_checks:
        findings.append(
            QualityGateFinding(
                code="missing_observable_checks",
                severity="error",
                location="observableChecks",
                message="Project Model v0 requires at least one observable check.",
            )
        )
    check_component_by_id = {
        str(check.get("id", "")): str(check.get("componentId", ""))
        for check in observable_checks
        if check.get("id")
    }
    valid_check_ids = set(check_component_by_id)

    for check_id, component_id in sorted(check_component_by_id.items()):
        if component_id not in component_id_set:
            findings.append(
                QualityGateFinding(
                    code="missing_observable_check_component",
                    severity="error",
                    location=f"observableChecks[{check_id}].componentId",
                    message=f"Observable check {check_id} references unknown component {component_id!r}.",
                )
            )

    for component in components:
        component_id = str(component.get("id", ""))
        declared_check_ids = {
            str(check_id)
            for check_id in _list_of_scalars(component.get("observableCheckIds"))
            if str(check_id)
        }
        for check_id in sorted(declared_check_ids - valid_check_ids):
            findings.append(
                QualityGateFinding(
                    code="missing_observable_check_reference",
                    severity="error",
                    location=f"components[{component_id}].observableCheckIds",
                    message=f"Component {component_id} references missing observable check {check_id}.",
                )
            )
        for check_id in sorted(declared_check_ids & valid_check_ids):
            if check_component_by_id.get(check_id) != component_id:
                findings.append(
                    QualityGateFinding(
                        code="observable_check_component_mismatch",
                        severity="error",
                        location=f"components[{component_id}].observableCheckIds",
                        message=(
                            f"Component {component_id} links observable check {check_id}, but that check "
                            f"belongs to {check_component_by_id.get(check_id)}."
                        ),
                    )
                )
        if not declared_check_ids:
            findings.append(
                QualityGateFinding(
                    code="component_without_observable_check",
                    severity="error",
                    location=f"components[{component_id}].observableCheckIds",
                    message=f"Component {component_id} has no linked observable check id.",
                )
            )
        if _is_vague_component(component):
            findings.append(
                QualityGateFinding(
                    code="vague_decomposition",
                    severity="error",
                    location=f"components[{component_id}]",
                    message=(
                        f"Component {component_id or '<missing>'} is too vague to be a load-bearing "
                        "project decomposition unit."
                    ),
                )
            )

    dependencies = _list_of_dicts(model.get("dependencies"))
    if len(component_id_set) > 1 and not dependencies:
        findings.append(
            QualityGateFinding(
                code="missing_dependencies",
                severity="error",
                location="dependencies",
                message="Model has multiple components but no dependency or sequencing constraints.",
            )
        )

    dependency_edges: list[tuple[str, str, str]] = []
    for dependency in dependencies:
        dependency_id = str(dependency.get("id", ""))
        from_component = str(dependency.get("fromComponent", ""))
        to_component = str(dependency.get("toComponent", ""))
        kind = str(dependency.get("kind", ""))
        if from_component not in component_id_set or to_component not in component_id_set:
            findings.append(
                QualityGateFinding(
                    code="missing_dependency_reference",
                    severity="error",
                    location=f"dependencies[{dependency_id}]",
                    message=(
                        f"Dependency {dependency_id or '<missing>'} references unknown component(s): "
                        f"{from_component!r} -> {to_component!r}."
                    ),
                )
            )
            continue
        if kind in _DIRECTIONAL_DEPENDENCY_KINDS:
            dependency_edges.append((from_component, to_component, dependency_id))

    findings.extend(_contradictory_dependency_findings(dependency_edges))

    unclassified_surfaces = _list_of_dicts(model.get("unclassifiedProjectSurface"))
    if unclassified_surfaces:
        findings.append(
            QualityGateFinding(
                code="unclassified_project_surface",
                severity="error",
                location="unclassifiedProjectSurface",
                message=(
                    "Model leaves significant project surface unclassified: "
                    + ", ".join(str(surface.get("id", "<missing>")) for surface in unclassified_surfaces)
                ),
            )
        )

    high_risk_components = _high_risk_component_ids(components, _list_of_dicts(model.get("risks")))
    held_out_component_ids = {
        str(probe.get("componentId", "")) for probe in _list_of_dicts(model.get("heldOutProbes"))
    }
    for component_id in sorted(high_risk_components):
        if component_id not in held_out_component_ids:
            findings.append(
                QualityGateFinding(
                    code="missing_held_out_probe",
                    severity="error",
                    location=f"heldOutProbes[{component_id}]",
                    message=f"High-risk component {component_id} has no held-out probe or counterexample.",
                )
            )

    return QualityGateReport(
        passed=not any(finding.severity == "error" for finding in findings),
        findings=findings,
    )


def _absent_alignment() -> ProjectModelAlignment:
    return ProjectModelAlignment(
        projectModelPresence="absent",
        projectModelValidity=ProjectModelValidity(status="absent", qualityGatePassed=None),
        goalAlignment=ProjectModelScalarAlignment(status="not_available"),
        componentAlignment=ProjectModelComponentAlignment(status="not_available"),
        nearNeighborResistance=ProjectModelNearNeighborResistance(status="not_available"),
        notes=[
            "No Project Model v0 was supplied; project-level alignment, F2/F3 separation, and held-out probe signals were not run."
        ],
    )


def _invalid_alignment(
    *,
    schema_version: str | None,
    findings: list[ProjectModelFinding],
    status: Literal["invalid", "unsupported_version"] = "invalid",
) -> ProjectModelAlignment:
    return ProjectModelAlignment(
        projectModelPresence="present",
        projectModelValidity=ProjectModelValidity(
            status=status,
            schemaVersion=schema_version,
            qualityGatePassed=False,
            findings=findings,
        ),
        goalAlignment=ProjectModelScalarAlignment(
            status="not_available",
            notes=["Project Model v0 alignment was not evaluated because the supplied model is invalid."],
        ),
        componentAlignment=ProjectModelComponentAlignment(status="not_available"),
        nearNeighborResistance=ProjectModelNearNeighborResistance(status="not_available"),
        failureModeHint=None,
        notes=[_ADVISORY_NOTE, "Invalid Project Model v0 is reported as input/model-quality, not as normal success."],
    )


def _component_alignment(
    model: ProjectModelV0, request: EvaluationRequest, rationale_text: str
) -> ProjectModelComponentAlignment:
    proposed_target = _normalize(request.proposedAction.target or "")
    proposed_type = _normalize(request.proposedAction.type)
    matched: list[str] = []
    missing: list[str] = []
    misdirected: list[str] = []
    for component in model.components:
        component_terms = _component_terms(component)
        id_norm = _normalize(component.id)
        target_hit = proposed_target == id_norm or proposed_type == id_norm
        positive_hit = target_hit or any(_contains_affirmed(rationale_text, term) for term in component_terms)
        negative_hit = any(_contains_negated(rationale_text, term) for term in component_terms)
        if positive_hit and not negative_hit:
            matched.append(component.id)
        else:
            missing.append(component.id)
            if negative_hit:
                misdirected.append(component.id)
    score = clamp01(len(matched) / len(model.components)) if model.components else 0.0
    status: Literal["aligned", "partial", "misaligned"]
    if score >= 0.75:
        status = "aligned"
    elif score > 0:
        status = "partial"
    else:
        status = "misaligned"
    return ProjectModelComponentAlignment(
        status=status,
        score=score,
        matchedIds=matched,
        missingIds=missing,
        misdirectedIds=misdirected,
        notes=["Component alignment checks whether public rationale targets the decomposed components, not whether the proposal is correct."],
    )


def _goal_alignment(
    model: ProjectModelV0, rationale_text: str, components: ProjectModelComponentAlignment
) -> ProjectModelScalarAlignment:
    goal_terms = _salient_terms(model.goal)
    matched_terms = [term for term in goal_terms if _contains_affirmed(rationale_text, term)]
    missing_terms = [term for term in goal_terms if term not in matched_terms]
    term_score = len(matched_terms) / len(goal_terms) if goal_terms else 0.0
    component_score = components.score or 0.0
    score = clamp01(term_score * 0.55 + component_score * 0.45)
    status: Literal["aligned", "partial", "misaligned"]
    if score >= 0.55:
        status = "aligned"
    elif score >= 0.25:
        status = "partial"
    else:
        status = "misaligned"
    return ProjectModelScalarAlignment(
        status=status,
        score=score,
        matchedTerms=matched_terms,
        missingTerms=missing_terms[:12],
        notes=["Goal alignment is a local lexical advisory proxy over the supplied Project Model goal."],
    )


def _invariant_violations(
    model: ProjectModelV0, rationale_text: str, components: ProjectModelComponentAlignment
) -> list[ProjectModelFinding]:
    findings: list[ProjectModelFinding] = []
    missing_ids = set(components.missingIds)
    for invariant in model.invariants:
        affected_missing = sorted(set(invariant.componentIds) & missing_ids)
        dashboard_only = "dashboard" in rationale_text and (
            "visible" in rationale_text or "only" in rationale_text or "sufficient" in rationale_text
        )
        missing_misdirected = "event_provenance" in affected_missing and bool(set(affected_missing) & set(components.misdirectedIds))
        missing_primary_before_dashboard = "event_provenance" in affected_missing and dashboard_only
        if affected_missing and (missing_misdirected or missing_primary_before_dashboard or "without event provenance" in rationale_text):
            findings.append(
                ProjectModelFinding(
                    code="invariant_unaddressed",
                    severity="warning",
                    location=f"invariants[{invariant.id}]",
                    message=(
                        f"Rationale does not positively address invariant {invariant.id}; "
                        f"missing component(s): {', '.join(affected_missing)}."
                    ),
                )
            )
    return findings


def _dependency_violations(
    model: ProjectModelV0, rationale_text: str, components: ProjectModelComponentAlignment
) -> list[ProjectModelFinding]:
    del rationale_text
    findings: list[ProjectModelFinding] = []
    matched = set(components.matchedIds)
    missing = set(components.missingIds)
    for dependency in model.dependencies:
        if dependency.kind not in _DIRECTIONAL_DEPENDENCY_KINDS:
            continue
        if dependency.toComponent in matched and dependency.fromComponent in missing:
            findings.append(
                ProjectModelFinding(
                    code="dependency_prerequisite_unaddressed",
                    severity="warning",
                    location=f"dependencies[{dependency.id}]",
                    message=(
                        f"Rationale targets {dependency.toComponent} while prerequisite "
                        f"{dependency.fromComponent} is not positively addressed."
                    ),
                )
            )
    return findings


def _unsupported_assumptions(model: ProjectModelV0, rationale_text: str, context_text: str) -> list[ProjectModelFinding]:
    findings: list[ProjectModelFinding] = []
    combined = f"{rationale_text} {context_text}"
    for assumption in model.assumptions:
        if assumption.status == "confirmed":
            continue
        terms = _salient_terms(f"{assumption.id} {assumption.description}")
        if terms and not any(_contains_affirmed(combined, term) for term in terms):
            findings.append(
                ProjectModelFinding(
                    code="unsupported_assumption",
                    severity="warning",
                    location=f"assumptions[{assumption.id}]",
                    message=f"Assumption {assumption.id} is not grounded in the supplied rationale or evidence text.",
                )
            )
    return findings


def _evidence_grounding_gaps(
    model: ProjectModelV0,
    rationale_text: str,
    evidence_text: str,
    components: ProjectModelComponentAlignment,
) -> list[ProjectModelFinding]:
    findings: list[ProjectModelFinding] = []
    combined = _normalize(f"{rationale_text} {evidence_text}")
    missing_components = set(components.missingIds)
    for requirement in model.evidenceRequirements:
        required_for = set(requirement.requiredFor)
        required_component_gap = bool(required_for & missing_components)
        terms = _salient_terms(
            " ".join([requirement.id, requirement.description, *requirement.acceptedArtifactTypes, *requirement.requiredFor])
        )
        support = sum(1 for term in terms if _contains_affirmed(combined, term))
        if required_component_gap or (terms and support < min(2, len(terms))):
            findings.append(
                ProjectModelFinding(
                    code="evidence_grounding_gap",
                    severity="warning",
                    location=f"evidenceRequirements[{requirement.id}]",
                    message=f"Evidence requirement {requirement.id} is not sufficiently represented in rationale/evidence text.",
                )
            )
    return findings


def _near_neighbor_resistance(
    model: ProjectModelV0, request: EvaluationRequest, rationale_text: str
) -> ProjectModelNearNeighborResistance:
    if not model.nearNeighborAlternatives:
        return ProjectModelNearNeighborResistance(status="not_available")
    rejected_ids = {
        alt.actionId
        for alt in (request.structuredRationale.rejectedAlternatives if request.structuredRationale else [])
        if alt.actionId
    }
    resisted: list[str] = []
    unaddressed: list[str] = []
    for alternative in model.nearNeighborAlternatives:
        terms = _salient_terms(
            " ".join([alternative.id, alternative.description, alternative.whyNotPrimary, *alternative.distinguishingEvidence])
        )
        explicit_reject = alternative.id in rejected_ids
        contrast_terms = {"rather", "instead", "weaker", "not", "only", "without"}
        lexical_contrast = any(term in rationale_text for term in contrast_terms) and any(
            _contains_affirmed(rationale_text, term) for term in terms
        )
        if explicit_reject or lexical_contrast:
            resisted.append(alternative.id)
        else:
            unaddressed.append(alternative.id)
    score = clamp01(len(resisted) / len(model.nearNeighborAlternatives))
    status: Literal["resistant", "partial", "weak"]
    if score >= 0.75:
        status = "resistant"
    elif score > 0:
        status = "partial"
    else:
        status = "weak"
    return ProjectModelNearNeighborResistance(
        status=status,
        score=score,
        resistedIds=resisted,
        unaddressedIds=unaddressed,
        notes=["Near-neighbor resistance checks whether supplied alternatives are distinguished, not which action is correct."],
    )


def _held_out_probe_failures(
    model: ProjectModelV0,
    rationale_text: str,
    evidence_text: str,
    components: ProjectModelComponentAlignment,
) -> list[ProjectModelFinding]:
    findings: list[ProjectModelFinding] = []
    combined = _normalize(f"{rationale_text} {evidence_text}")
    missing_components = set(components.missingIds)
    for probe in model.heldOutProbes:
        terms = _salient_terms(
            " ".join([probe.id, probe.scenario, probe.expectedBehavior, *probe.evidenceRequired])
        )
        matched = sum(1 for term in terms if _contains_affirmed(combined, term))
        if probe.componentId in missing_components or (terms and matched < min(2, len(terms))):
            findings.append(
                ProjectModelFinding(
                    code="held_out_probe_unaddressed",
                    severity="warning",
                    location=f"heldOutProbes[{probe.id}]",
                    message=f"Held-out probe {probe.id} is not addressed by the public rationale/evidence text.",
                )
            )
    return findings


def _failure_mode_hint(
    *,
    rationale_text: str,
    component_alignment: ProjectModelComponentAlignment,
    goal_alignment: ProjectModelScalarAlignment,
    invariant_violations: list[ProjectModelFinding],
    dependency_violations: list[ProjectModelFinding],
    evidence_gaps: list[ProjectModelFinding],
    held_out_failures: list[ProjectModelFinding],
) -> tuple[Literal["F1", "F2", "F3", "F4"] | None, str | None]:
    token_set = set(_word_tokens(rationale_text))
    decorative_hits = len(token_set & _DECORATIVE_TERMS)
    concrete_hits = len(token_set - _DECORATIVE_TERMS - _STOPWORDS)
    has_component_hit = bool(component_alignment.matchedIds)
    serious_alignment_gaps = bool(
        component_alignment.missingIds
        and (invariant_violations or dependency_violations or evidence_gaps or held_out_failures)
    )
    if decorative_hits >= 2 and concrete_hits < 14 and (not has_component_hit or (component_alignment.score or 0.0) <= 0.5):
        return "F2", "F2: rationale is decorative/vague and lacks load-bearing Project Model component or evidence alignment."
    if has_component_hit and serious_alignment_gaps:
        return (
            "F3",
            "F3: rationale is load-bearing but appears aimed at the wrong component, level, sequence, or visible example.",
        )
    if goal_alignment.status in {"aligned", "partial"} and not (
        invariant_violations or dependency_violations or evidence_gaps or held_out_failures
    ):
        return "F1", "F1: no deterministic Project Model alignment gaps were detected in this advisory pass."
    if invariant_violations or dependency_violations or evidence_gaps or held_out_failures:
        return "F4", "F4: deterministic pass found project-model gaps but not enough load-bearing misdirection for F3."
    return None, None


def _finding_from_quality(finding: QualityGateFinding) -> ProjectModelFinding:
    return ProjectModelFinding(
        code=finding.code,
        severity="error" if finding.severity == "error" else "warning",
        location=finding.location,
        message=finding.message,
    )


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _list_of_scalars(value: Any) -> list[Any]:
    if not isinstance(value, list):
        return []
    return [item for item in value if not isinstance(item, (dict, list))]


def _normalized_token(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _normalize(value: Any) -> str:
    text = str(value or "").lower().replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", text).strip()


def _word_tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", _normalize(value))


def _salient_terms(value: str) -> list[str]:
    normalized = _normalize(value)
    words = [word for word in _word_tokens(normalized) if len(word) > 2 and word not in _STOPWORDS]
    phrases: list[str] = []
    raw_terms = [normalized]
    for size in (3, 2):
        for idx in range(0, max(0, len(words) - size + 1)):
            phrase = " ".join(words[idx : idx + size])
            if len(phrase) >= 8:
                phrases.append(phrase)
    raw_terms.extend(words)
    raw_terms.extend(phrases)
    seen: dict[str, None] = {}
    for term in raw_terms:
        term = _normalize(term)
        if term and term not in _STOPWORDS and len(term) > 2:
            seen.setdefault(term, None)
    return list(seen)[:24]


def _component_terms(component: Component) -> list[str]:
    terms = [component.id, component.name]
    terms.extend(component.ownedSurfaces)
    return _salient_terms(" ".join(terms))


def _contains_affirmed(text: str, term: str) -> bool:
    normalized = _normalize(term)
    if not normalized:
        return False
    if normalized not in text:
        return False
    return not _contains_negated(text, normalized)


def _contains_negated(text: str, term: str) -> bool:
    normalized = _normalize(term)
    if not normalized:
        return False
    if any(pattern.format(term=normalized) in text for pattern in _NEGATION_WINDOWS):
        return True
    for match in re.finditer(re.escape(normalized), text):
        prior = text[max(0, match.start() - 40) : match.start()]
        if any(marker in prior for marker in ("rather than", "instead of", "without", "not ", "no ", "reject", "skip")):
            return True
    return False


def _request_rationale_text(request: EvaluationRequest) -> str:
    parts = [request.rationale, request.proposedAction.type, request.proposedAction.target or ""]
    structured = request.structuredRationale
    if structured is not None:
        parts.append(structured.claim)
        parts.extend(ground.text for ground in structured.grounds)
        parts.extend(structured.warrants)
        parts.extend(structured.assumptions)
        parts.extend(structured.uncertainty)
        parts.extend(structured.wouldChangeIf)
        parts.extend(alternative.reason for alternative in structured.rejectedAlternatives)
    return _normalize(" ".join(parts))


def _evidence_text(request: EvaluationRequest) -> str:
    if request.evidenceBundle is None:
        return ""
    return _normalize(
        " ".join(
            " ".join([artifact.id, artifact.type, artifact.contentPointer or "", artifact.content or ""])
            for artifact in request.evidenceBundle
        )
    )


def _is_vague_component(component: dict[str, Any]) -> bool:
    component_id = _normalized_token(component.get("id"))
    name = _normalized_token(component.get("name"))
    if component_id in _VAGUE_IDS or name in _VAGUE_IDS:
        return True

    responsibilities = " ".join(str(item) for item in _list_of_scalars(component.get("responsibilities"))).lower()
    if any(phrase in responsibilities for phrase in _VAGUE_PHRASES):
        return True

    owned_surfaces = {
        str(surface).strip().lower() for surface in _list_of_scalars(component.get("ownedSurfaces"))
    }
    return bool(owned_surfaces) and owned_surfaces <= _VAGUE_SURFACES


def _contradictory_dependency_findings(
    dependency_edges: list[tuple[str, str, str]],
) -> list[QualityGateFinding]:
    findings: list[QualityGateFinding] = []
    seen: dict[tuple[str, str], str] = {}
    for source, target, dependency_id in dependency_edges:
        reverse = (target, source)
        if reverse in seen:
            findings.append(
                QualityGateFinding(
                    code="contradictory_dependencies",
                    severity="error",
                    location=f"dependencies[{dependency_id}]",
                    message=(
                        f"Dependency {dependency_id or '<missing>'} contradicts {seen[reverse]}: "
                        f"{source} and {target} are each ordered before the other."
                    ),
                )
            )
        seen[(source, target)] = dependency_id

    graph: dict[str, set[str]] = defaultdict(set)
    for source, target, _dependency_id in dependency_edges:
        graph[source].add(target)
    cycle_path = _first_cycle(graph)
    if cycle_path:
        findings.append(
            QualityGateFinding(
                code="contradictory_dependencies",
                severity="error",
                location="dependencies",
                message="Directional dependency cycle detected: " + " -> ".join(cycle_path),
            )
        )
    return findings


def _first_cycle(graph: dict[str, set[str]]) -> list[str]:
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(node: str) -> list[str]:
        if node in visiting:
            try:
                start = stack.index(node)
            except ValueError:
                start = 0
            return [*stack[start:], node]
        if node in visited:
            return []
        visiting.add(node)
        stack.append(node)
        for neighbor in sorted(graph.get(node, set())):
            cycle = visit(neighbor)
            if cycle:
                return cycle
        stack.pop()
        visiting.remove(node)
        visited.add(node)
        return []

    for node in sorted(graph):
        cycle = visit(node)
        if cycle:
            return cycle
    return []


def _high_risk_component_ids(
    components: list[dict[str, Any]],
    risks: list[dict[str, Any]],
) -> set[str]:
    high_risk = {
        str(component.get("id", ""))
        for component in components
        if str(component.get("riskLevel", "")).lower() == "high" and component.get("id")
    }
    high_risk.update(
        str(risk.get("componentId", ""))
        for risk in risks
        if str(risk.get("level", "")).lower() == "high" and risk.get("componentId")
    )
    return high_risk
