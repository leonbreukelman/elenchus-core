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
PROJECT_MODEL_V1_SCHEMA_VERSION = "project-model/v1"
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")

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
    "Project Model v0/v1 alignment is an advisory deterministic signal; it is not objective truth, "
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
    schema_version = raw_model.get("schemaVersion")
    if schema_version == PROJECT_MODEL_V1_SCHEMA_VERSION:
        return _assess_project_model_v1_alignment(request, raw_model)

    quality_report = evaluate_quality_gate(raw_model)
    status: Literal["invalid", "unsupported_version"] = (
        "unsupported_version" if schema_version != PROJECT_MODEL_V0_SCHEMA_VERSION else "invalid"
    )
    if not quality_report.passed:
        return _invalid_alignment(
            schema_version=str(schema_version) if schema_version is not None else None,
            findings=[_finding_from_quality(finding) for finding in quality_report.findings],
            status=status,
        )

    return _assess_project_model_v0_alignment(request, raw_model)


def _assess_project_model_v0_alignment(
    request: EvaluationRequest, raw_model: dict[str, Any]
) -> ProjectModelAlignment:
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


def _assess_project_model_v1_alignment(request: EvaluationRequest, raw_model: dict[str, Any]) -> ProjectModelAlignment:
    shape_findings = _project_model_v1_shape_findings(raw_model)
    gate_findings = _project_model_v1_gate_findings(raw_model)
    if shape_findings or gate_findings:
        return _invalid_alignment(
            schema_version=PROJECT_MODEL_V1_SCHEMA_VERSION,
            findings=[*shape_findings, *gate_findings],
            status="invalid",
        )

    rationale_text = _request_rationale_text(request)
    evidence_text = _evidence_text(request)
    component_alignment = _project_model_v1_component_alignment(raw_model, request, rationale_text)
    goal_alignment = _project_model_v1_goal_alignment(raw_model, rationale_text, component_alignment)
    dependency_violations = _project_model_v1_contract_findings(raw_model)
    evidence_gaps = [
        *_project_model_v1_provenance_findings(raw_model),
        *_project_model_v1_observable_check_findings(raw_model),
    ]
    near_neighbor_resistance = _project_model_v1_near_neighbor_resistance(raw_model, request, rationale_text)
    held_out_failures = _project_model_v1_held_out_probe_failures(raw_model, evidence_text)
    hint, reason = _failure_mode_hint(
        rationale_text=rationale_text,
        component_alignment=component_alignment,
        goal_alignment=goal_alignment,
        invariant_violations=[],
        dependency_violations=dependency_violations,
        evidence_gaps=evidence_gaps,
        held_out_failures=held_out_failures,
    )
    return ProjectModelAlignment(
        projectModelPresence="present",
        projectModelValidity=ProjectModelValidity(
            status="valid",
            schemaVersion=PROJECT_MODEL_V1_SCHEMA_VERSION,
            qualityGatePassed=True,
            findings=[],
        ),
        goalAlignment=goal_alignment,
        componentAlignment=component_alignment,
        invariantViolations=[],
        dependencyViolations=dependency_violations,
        unsupportedAssumptions=[],
        evidenceGroundingGaps=evidence_gaps,
        nearNeighborResistance=near_neighbor_resistance,
        heldOutProbeFailures=held_out_failures,
        failureModeHint=hint,
        failureModeHintReason=reason,
        notes=[_ADVISORY_NOTE, "Project Model v1 is consumed as Build Arena-owned advisory input only."],
    )


def _project_model_v1_shape_findings(model: dict[str, Any]) -> list[ProjectModelFinding]:
    findings: list[ProjectModelFinding] = []
    for field in ("project", "snapshot", "projectGraph", "gateReport", "provenance"):
        if not isinstance(model.get(field), dict):
            findings.append(
                ProjectModelFinding(
                    code="missing_project_model_v1_field",
                    severity="error",
                    location=field,
                    message=f"Project Model v1 requires object field {field!r} from the Build Arena contract.",
                )
            )
    provenance = _dict_value(model.get("provenance"))
    git = _dict_value(provenance.get("git"))
    if not git:
        findings.append(
            ProjectModelFinding(
                code="missing_project_model_v1_field",
                severity="error",
                location="provenance.git",
                message="Project Model v1 requires provenance.git from the Build Arena contract.",
            )
        )
    fingerprint = git.get("dirtyStateFingerprint")
    if not isinstance(fingerprint, str) or not fingerprint.strip():
        findings.append(
            ProjectModelFinding(
                code="missing_dirty_state_fingerprint",
                severity="error",
                location="provenance.git.dirtyStateFingerprint",
                message="Project Model v1 requires a non-empty dirtyStateFingerprint so dirty-tree provenance is explicit.",
            )
        )
    elif SHA256_RE.fullmatch(fingerprint) is None:
        findings.append(
            ProjectModelFinding(
                code="invalid_dirty_state_fingerprint",
                severity="error",
                location="provenance.git.dirtyStateFingerprint",
                message="Project Model v1 dirtyStateFingerprint must be a lowercase sha256 digest matching the Build Arena schema.",
            )
        )
    return findings


def _project_model_v1_gate_findings(model: dict[str, Any]) -> list[ProjectModelFinding]:
    gate_report = _dict_value(model.get("gateReport"))
    passed = gate_report.get("passed")
    if not isinstance(passed, bool):
        return [
            ProjectModelFinding(
                code="invalid_project_model_v1_gate_report",
                severity="error",
                location="gateReport.passed",
                message="Build Arena Project Model v1 gateReport.passed must be a boolean.",
            )
        ]
    if passed is True:
        return []
    violations = _list_of_dicts(gate_report.get("violations"))
    if not violations:
        return [
            ProjectModelFinding(
                code="project_model_v1_gate_failed",
                severity="error",
                location="gateReport",
                message="Build Arena Project Model v1 gateReport failed without a structured violation.",
            )
        ]
    findings: list[ProjectModelFinding] = []
    for index, violation in enumerate(violations):
        gate = str(violation.get("gate") or "gateReport")
        location = str(violation.get("location") or f"gateReport.violations[{index}]")
        message = str(violation.get("message") or "Build Arena Project Model v1 gateReport failed.")
        findings.append(
            ProjectModelFinding(
                code="project_model_v1_gate_failed",
                severity="error",
                location=location,
                message=f"Build Arena Project Model v1 gate {gate!r} failed: {message}",
            )
        )
    return findings


def _project_model_v1_component_alignment(
    model: dict[str, Any], request: EvaluationRequest, rationale_text: str
) -> ProjectModelComponentAlignment:
    components = _list_of_dicts(_dict_value(model.get("snapshot")).get("components"))
    if not components:
        return ProjectModelComponentAlignment(status="not_available")
    proposed_target = _normalize(request.proposedAction.target or "")
    proposed_type = _normalize(request.proposedAction.type)
    matched: list[str] = []
    missing: list[str] = []
    misdirected: list[str] = []
    for component in components:
        component_id = str(component.get("id") or "<missing>")
        component_terms = _project_model_v1_component_terms(component)
        id_norm = _normalize(component_id)
        target_hit = proposed_target == id_norm or proposed_type == id_norm
        positive_hit = target_hit or any(_contains_affirmed(rationale_text, term) for term in component_terms)
        negative_hit = not target_hit and any(_contains_negated(rationale_text, term) for term in component_terms)
        if positive_hit and not negative_hit:
            matched.append(component_id)
        else:
            missing.append(component_id)
            if negative_hit:
                misdirected.append(component_id)
    score = clamp01(len(matched) / len(components))
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
        notes=["Project Model v1 component alignment is advisory and does not judge action correctness."],
    )


def _project_model_v1_goal_alignment(
    model: dict[str, Any], rationale_text: str, components: ProjectModelComponentAlignment
) -> ProjectModelScalarAlignment:
    project = _dict_value(model.get("project"))
    snapshot = _dict_value(model.get("snapshot"))
    goal_text = " ".join(
        [
            str(project.get("goal") or ""),
            str(snapshot.get("goal") or ""),
            " ".join(str(component.get("name") or "") for component in _list_of_dicts(snapshot.get("components"))),
        ]
    )
    goal_terms = _salient_terms(goal_text)
    matched_terms = [term for term in goal_terms if _contains_affirmed(rationale_text, term)]
    missing_terms = [term for term in goal_terms if term not in matched_terms]
    term_score = len(matched_terms) / len(goal_terms) if goal_terms else 0.0
    component_score = components.score or 0.0
    score = clamp01(term_score * 0.6 + component_score * 0.4)
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
        notes=["Goal alignment is a local lexical advisory proxy over the supplied Project Model v1 goal."],
    )


def _project_model_v1_contract_findings(model: dict[str, Any]) -> list[ProjectModelFinding]:
    snapshot = _dict_value(model.get("snapshot"))
    graph = _dict_value(model.get("projectGraph"))
    component_ids = {str(component.get("id") or "") for component in _list_of_dicts(snapshot.get("components"))}
    edge_ids = {str(edge.get("id") or "") for edge in _list_of_dicts(graph.get("edges"))}
    findings: list[ProjectModelFinding] = []
    for contract in _list_of_dicts(snapshot.get("contracts")):
        contract_id = str(contract.get("id") or "<missing>")
        from_component = str(contract.get("from_component_id") or "")
        to_component = str(contract.get("to_component_id") or "")
        unknown_components = sorted({from_component, to_component} - component_ids - {""})
        if unknown_components:
            findings.append(
                ProjectModelFinding(
                    code="project_model_v1_contract_unknown_component",
                    severity="warning",
                    location=f"snapshot.contracts[{contract_id}]",
                    message=(
                        f"Contract {contract_id} references unknown component(s): "
                        f"{', '.join(unknown_components)}."
                    ),
                )
            )
        supporting_edge_ids = _string_list(contract.get("supporting_edge_ids"))
        if not supporting_edge_ids:
            findings.append(
                ProjectModelFinding(
                    code="project_model_v1_contract_missing_supporting_edge",
                    severity="warning",
                    location=f"snapshot.contracts[{contract_id}].supporting_edge_ids",
                    message=f"Contract {contract_id} does not cite a ProjectGraph edge as support.",
                )
            )
        unknown_edges = sorted(set(supporting_edge_ids) - edge_ids)
        for edge_id in unknown_edges:
            findings.append(
                ProjectModelFinding(
                    code="project_model_v1_contract_unknown_supporting_edge",
                    severity="warning",
                    location=f"snapshot.contracts[{contract_id}].supporting_edge_ids",
                    message=f"Contract {contract_id} cites unknown ProjectGraph edge {edge_id!r}.",
                )
            )
    return findings


def _project_model_v1_provenance_findings(model: dict[str, Any]) -> list[ProjectModelFinding]:
    graph = _dict_value(model.get("projectGraph"))
    snapshot = _dict_value(model.get("snapshot"))
    findings: list[ProjectModelFinding] = []
    provenance_ids: set[str] = set()
    for collection_name in ("nodes", "edges"):
        for item in _list_of_dicts(graph.get(collection_name)):
            item_id = str(item.get("id") or "<missing>")
            graph_refs = _list_of_dicts(item.get("provenance_refs"))
            if not graph_refs:
                findings.append(
                    ProjectModelFinding(
                        code="missing_project_graph_provenance",
                        severity="warning",
                        location=f"projectGraph.{collection_name}[{item_id}].provenance_refs",
                        message=f"ProjectGraph {collection_name[:-1]} {item_id} has no provenance_refs.",
                    )
                )
            for ref in graph_refs:
                ref_id = str(ref.get("id") or "")
                if ref_id:
                    provenance_ids.add(ref_id)
                else:
                    findings.append(
                        ProjectModelFinding(
                            code="missing_project_graph_provenance_id",
                            severity="warning",
                            location=f"projectGraph.{collection_name}[{item_id}].provenance_refs",
                            message=f"ProjectGraph {collection_name[:-1]} {item_id} includes a provenance ref without an id.",
                        )
                    )
    for collection_name in (
        "components",
        "contracts",
        "cross_cutting_concerns",
        "observable_checks",
        "held_out_probes",
        "verification_gaps",
        "near_neighbor_alternatives",
    ):
        for item in _list_of_dicts(snapshot.get(collection_name)):
            item_id = str(item.get("id") or "<missing>")
            snapshot_refs = _string_list(item.get("provenance_refs"))
            if not snapshot_refs:
                findings.append(
                    ProjectModelFinding(
                        code="missing_project_model_provenance_ref",
                        severity="warning",
                        location=f"snapshot.{collection_name}[{item_id}].provenance_refs",
                        message=f"Project Model v1 snapshot {collection_name} item {item_id} has no provenance_refs.",
                    )
                )
            for ref_id in snapshot_refs:
                if ref_id not in provenance_ids:
                    findings.append(
                        ProjectModelFinding(
                            code="unknown_project_model_provenance_ref",
                            severity="warning",
                            location=f"snapshot.{collection_name}[{item_id}].provenance_refs",
                            message=(
                                f"Project Model v1 snapshot {collection_name} item {item_id} references unknown "
                                f"ProjectGraph provenance id {ref_id!r}; this is only an internal consistency check, "
                                "not external authenticity proof."
                            ),
                        )
                    )
    for gap in _list_of_dicts(snapshot.get("verification_gaps")):
        gap_id = str(gap.get("id") or "<missing>")
        severity = _normalize(gap.get("severity"))
        if severity in {"high", "blocker", "critical"}:
            findings.append(
                ProjectModelFinding(
                    code="high_or_blocker_verification_gap",
                    severity="error",
                    location=f"snapshot.verification_gaps[{gap_id}]",
                    message=(
                        f"Project Model v1 verification gap {gap_id} is {severity or 'high priority'} and requires "
                        "operator review before treating the advisory signal as strong."
                    ),
                )
            )
    git = _dict_value(_dict_value(model.get("provenance")).get("git"))
    if git.get("dirty") is True:
        dirty_paths = ", ".join(_string_list(git.get("dirtyPaths"))) or "<unspecified paths>"
        fingerprint = str(git.get("dirtyStateFingerprint") or "<missing>")
        findings.append(
            ProjectModelFinding(
                code="dirty_project_model_provenance",
                severity="warning",
                location="provenance.git",
                message=(
                    f"Project Model v1 was generated from a dirty git tree ({dirty_paths}); "
                    f"dirtyStateFingerprint={fingerprint}. This fingerprints local state but does not prove external authenticity."
                ),
            )
        )
    return findings


def _project_model_v1_observable_check_findings(model: dict[str, Any]) -> list[ProjectModelFinding]:
    snapshot = _dict_value(model.get("snapshot"))
    checks = _list_of_dicts(snapshot.get("observable_checks"))
    if not checks:
        return [
            ProjectModelFinding(
                code="missing_observable_check",
                severity="warning",
                location="snapshot.observable_checks",
                message="Project Model v1 has no observable checks, so executable verification evidence is absent.",
            )
        ]
    allowlist = set(_string_list(snapshot.get("acceptance_command_allowlist")))
    findings: list[ProjectModelFinding] = []
    for check in checks:
        check_id = str(check.get("id") or "<missing>")
        location = f"snapshot.observable_checks[{check_id}]"
        command = str(check.get("command") or "").strip()
        if not command:
            findings.append(
                ProjectModelFinding(
                    code="observable_check_missing_command",
                    severity="warning",
                    location=f"{location}.command",
                    message=f"Observable check {check_id} has no command, so Elenchus cannot reason about its verification surface.",
                )
            )
        elif allowlist and command not in allowlist:
            findings.append(
                ProjectModelFinding(
                    code="observable_check_not_allowlisted",
                    severity="warning",
                    location=f"{location}.command",
                    message=f"Observable check {check_id} command is not present in snapshot.acceptance_command_allowlist.",
                )
            )
        if check.get("safe_to_run_by_default") is False:
            findings.append(
                ProjectModelFinding(
                    code="observable_check_not_safe_by_default",
                    severity="warning",
                    location=f"{location}.safe_to_run_by_default",
                    message=f"Observable check {check_id} is not safe to run by default; treat it as advisory until explicitly run.",
                )
            )
        if check.get("requires_network") is True:
            findings.append(
                ProjectModelFinding(
                    code="observable_check_requires_network",
                    severity="warning",
                    location=f"{location}.requires_network",
                    message=f"Observable check {check_id} requires network access; Elenchus did not execute it automatically.",
                )
            )
        if check.get("requires_paid_api") is True:
            findings.append(
                ProjectModelFinding(
                    code="observable_check_requires_paid_api",
                    severity="warning",
                    location=f"{location}.requires_paid_api",
                    message=f"Observable check {check_id} requires a paid API; Elenchus did not execute it automatically.",
                )
            )
    return findings



def _project_model_v1_held_out_probe_failures(
    model: dict[str, Any], evidence_text: str
) -> list[ProjectModelFinding]:
    del evidence_text
    probes = _list_of_dicts(_dict_value(model.get("snapshot")).get("held_out_probes"))
    if not probes:
        return [
            ProjectModelFinding(
                code="missing_held_out_probe",
                severity="warning",
                location="snapshot.held_out_probes",
                message="Project Model v1 has no held-out probes, so independent generalization evidence is absent.",
            )
        ]
    findings: list[ProjectModelFinding] = []
    for probe in probes:
        probe_id = str(probe.get("id") or "<missing>")
        if probe.get("builder_independent_from_decomposer") is False:
            findings.append(
                ProjectModelFinding(
                    code="held_out_probe_not_independent",
                    severity="warning",
                    location=f"snapshot.held_out_probes[{probe_id}].builder_independent_from_decomposer",
                    message=f"Held-out probe {probe_id} was not built independently from the decomposer.",
                )
            )
        if probe.get("hidden_from_primary_decomposer") is False:
            findings.append(
                ProjectModelFinding(
                    code="held_out_probe_not_hidden",
                    severity="warning",
                    location=f"snapshot.held_out_probes[{probe_id}].hidden_from_primary_decomposer",
                    message=f"Held-out probe {probe_id} was visible to the primary decomposer.",
                )
            )
        failed_checks = [
            field
            for field in ("discrimination_passed", "golden_control_passed")
            if probe.get(field) is False
        ]
        if failed_checks:
            findings.append(
                ProjectModelFinding(
                    code="held_out_probe_failed",
                    severity="warning",
                    location=f"snapshot.held_out_probes[{probe_id}]",
                    message=f"Held-out probe {probe_id} failed check(s): {', '.join(failed_checks)}.",
                )
            )
    return findings


def _project_model_v1_near_neighbor_resistance(
    model: dict[str, Any], request: EvaluationRequest, rationale_text: str
) -> ProjectModelNearNeighborResistance:
    alternatives = _list_of_dicts(_dict_value(model.get("snapshot")).get("near_neighbor_alternatives"))
    if not alternatives:
        return ProjectModelNearNeighborResistance(status="not_available")
    rejected_ids = {
        alt.actionId
        for alt in (request.structuredRationale.rejectedAlternatives if request.structuredRationale else [])
        if alt.actionId
    }
    resisted: list[str] = []
    unaddressed: list[str] = []
    for alternative in alternatives:
        alternative_id = str(alternative.get("id") or "<missing>")
        terms = _salient_terms(
            " ".join(
                [
                    alternative_id,
                    str(alternative.get("alternative") or ""),
                    str(alternative.get("why_not_primary") or ""),
                    str(alternative.get("target_id") or ""),
                ]
            )
        )
        explicit_reject = alternative_id in rejected_ids
        contrast_terms = {"rather", "instead", "weaker", "not", "only", "without"}
        lexical_contrast = any(term in rationale_text for term in contrast_terms) and any(
            _contains_affirmed(rationale_text, term) for term in terms
        )
        if explicit_reject or lexical_contrast:
            resisted.append(alternative_id)
        else:
            unaddressed.append(alternative_id)
    score = clamp01(len(resisted) / len(alternatives))
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
        notes=["Project Model v1 near-neighbor resistance is advisory and not an autonomous allow/deny gate."],
    )


def _absent_alignment() -> ProjectModelAlignment:
    return ProjectModelAlignment(
        projectModelPresence="absent",
        projectModelValidity=ProjectModelValidity(status="absent", qualityGatePassed=None),
        goalAlignment=ProjectModelScalarAlignment(status="not_available"),
        componentAlignment=ProjectModelComponentAlignment(status="not_available"),
        nearNeighborResistance=ProjectModelNearNeighborResistance(status="not_available"),
        notes=[
            "No Project Model v0/v1 was supplied; project-level alignment, F2/F3 separation, and held-out probe signals were not run."
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
            notes=["Project Model v0/v1 alignment was not evaluated because the supplied model is invalid."],
        ),
        componentAlignment=ProjectModelComponentAlignment(status="not_available"),
        nearNeighborResistance=ProjectModelNearNeighborResistance(status="not_available"),
        failureModeHint=None,
        notes=[_ADVISORY_NOTE, "Invalid Project Model v0/v1 is reported as input/model-quality, not as normal success."],
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


def _dict_value(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in _list_of_scalars(value) if str(item).strip()]


def _project_model_v1_component_terms(component: dict[str, Any]) -> list[str]:
    return _salient_terms(
        " ".join(
            [
                str(component.get("id") or ""),
                str(component.get("name") or ""),
                str(component.get("responsibility") or ""),
                " ".join(_string_list(component.get("owned_node_ids"))),
                " ".join(_string_list(component.get("contract_ids"))),
                " ".join(_string_list(component.get("check_ids"))),
            ]
        )
    )


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
            except ValueError:  # pragma: no cover - visiting nodes are always pushed onto stack.
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
