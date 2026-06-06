import csv
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from elenchus_core import cli
from elenchus_core.actions import generate_near_neighbor_alternatives
from elenchus_core.eval_cases import EvalCase, PairedEvalCase, load_eval_cases, load_paired_eval_cases
from elenchus_core.eval_suite import check_case, compute_label_counts, evaluate_pair, metric_value
from elenchus_core.evaluator import evaluate_request
from elenchus_core.evidence import (
    _action_evidence_present,
    _polarity_contradicts,
    _ref_assessment,
    _support_for_ground,
    assess_evidence_resolution,
)
from elenchus_core.grounding import METRIC_FAMILIES, _evidence, assess_context_grounding
from elenchus_core.http import app
from elenchus_core.models import (
    ContextGroundingAssessment,
    ContextGroundingSummary,
    EvaluationRequest,
    EvaluationSubscores,
    EvidenceArtifact,
    EvidenceResolutionAssessment,
    EvidenceResolutionSummary,
    PolicyFinding,
    RationaleGround,
    SupportAssessment,
    TypedAction,
)
from elenchus_core.policy import evaluate_sre_policy
from elenchus_core.project_model import (
    ProjectModelV0,
    _contains_affirmed,
    _contains_negated,
    _contradictory_dependency_findings,
    _evidence_text,
    _failure_mode_hint,
    _first_cycle,
    _is_vague_component,
    _list_of_scalars,
    assess_project_model_alignment,
    evaluate_quality_gate,
)
from elenchus_core.providers import (
    _model_for,
    _term_support,
    infer_provider_from_preferred_model,
    normalize_provider_name,
    resolve_default_provider_config,
)
from elenchus_core.report import (
    _base_recommendation,
    _cap_recommendation,
    _project_model_has_alignment_gaps,
    build_error_report,
    confidence,
    method_trust_for,
    readiness,
    recommend,
    support_with_margin_reliability,
    top_weaknesses,
)


def _request(
    *,
    trace_id: str = "coverage-request-001",
    domain: str = "sre",
    action_type: str = "terminate_idle_sessions",
    target: str | None = "postgres-primary",
    risk_level: str | None = "medium",
    context: str | None = None,
    rationale: str | None = None,
    structured: dict | None = None,
    evidence_bundle: list[dict] | None = None,
    project_model: dict | None = None,
) -> EvaluationRequest:
    payload = {
        "traceId": trace_id,
        "domain": domain,
        "context": context
        or "Postgres has 12 idle sessions holding locks on audit_logs and VACUUM is blocked.",
        "proposedAction": {"type": action_type, "target": target, "riskLevel": risk_level},
        "rationale": rationale
        or "Because 12 idle sessions hold locks on audit_logs, terminate idle sessions to unblock VACUUM.",
    }
    if structured is not None:
        payload["structuredRationale"] = structured
    if evidence_bundle is not None:
        payload["evidenceBundle"] = evidence_bundle
    if project_model is not None:
        payload["projectModel"] = project_model
    return EvaluationRequest.model_validate(payload)


def _case_payload(case_id: str = "coverage-case-001") -> dict:
    return {
        "id": case_id,
        "split": "smoke",
        "source": {
            "benchmark": "coverage_synthetic",
            "sourceId": case_id,
            "license": "internal synthetic",
            "transformation": "coverage characterization fixture",
        },
        "scenarioTags": ["sre_native"],
        "request": _request(trace_id=case_id).model_dump(mode="json", by_alias=True, exclude_none=True),
        "expected": {"label": "supported", "recommendationMax": "proceed"},
    }


def _eval_case(case_id: str = "coverage-case-001") -> EvalCase:
    return EvalCase.model_validate(_case_payload(case_id))


def _paired_payload() -> dict:
    supported = _case_payload("coverage-pair-supported")
    supported["split"] = "paired"
    challenged = json.loads(json.dumps(supported))
    challenged["id"] = "coverage-pair-challenged"
    challenged["request"]["traceId"] = "coverage-pair-challenged"
    challenged["expected"]["label"] = "unsupported"
    return {"pairId": "coverage-pair", "supported": supported, "challenged": challenged}


def _project_model(component_count: int = 1) -> dict:
    components = [
        {
            "id": "event_provenance",
            "name": "Event provenance",
            "kind": "architecture",
            "riskLevel": "low",
            "responsibilities": ["Track replayable event provenance for signal ids."],
            "ownedSurfaces": ["event log"],
            "observableCheckIds": ["check_event_provenance"],
        }
    ]
    checks = [
        {
            "id": "check_event_provenance",
            "componentId": "event_provenance",
            "mode": "inspection",
            "description": "Inspect event provenance for replayable signal ids.",
            "observableSignal": "Replayable signal ids are visible in the event log.",
            "evidenceRequired": ["event log"],
            "noLiveApi": True,
        }
    ]
    if component_count > 1:
        components.append(
            {
                "id": "dashboard_rendering",
                "name": "Dashboard rendering",
                "kind": "source",
                "riskLevel": "low",
                "responsibilities": ["Render dashboard state from provenance."],
                "ownedSurfaces": ["dashboard route"],
                "observableCheckIds": ["check_dashboard_rendering"],
            }
        )
        checks.append(
            {
                "id": "check_dashboard_rendering",
                "componentId": "dashboard_rendering",
                "mode": "inspection",
                "description": "Inspect dashboard rendering from typed state.",
                "observableSignal": "Dashboard route uses typed state.",
                "evidenceRequired": ["dashboard sample"],
                "noLiveApi": True,
            }
        )
    return {
        "schemaVersion": "project-model/v0",
        "id": "coverage_project_model",
        "source": {"task": "Evaluate a project model.", "primaryBacklogItem": "issue-1"},
        "goal": "Ship replayable event provenance before dashboard rendering polish.",
        "nonGoals": [],
        "components": components,
        "dependencies": [],
        "invariants": [],
        "observableChecks": checks,
        "evidenceRequirements": [],
        "assumptions": [],
        "risks": [],
        "nearNeighborAlternatives": [],
        "heldOutProbes": [],
        "verificationGaps": [],
        "unclassifiedProjectSurface": [],
        "advisorySignalHandoff": {
            "consumer": "elenchus-core",
            "expectedFields": [
                "projectModelPresence",
                "projectModelValidity",
                "goalAlignment",
                "componentAlignment",
                "invariantViolations",
                "dependencyViolations",
            ],
            "optionalFLabelHint": True,
        },
    }


def _grounding(score: float = 0.8, contradicted: int = 0, load_bearing: int = 1) -> ContextGroundingAssessment:
    return ContextGroundingAssessment(
        score=score,
        anchors=[],
        summary=ContextGroundingSummary(present=load_bearing - contradicted, absent=0, contradicted=contradicted, loadBearing=load_bearing),
        notes=[],
    )


def _support(margin: float = 0.3) -> SupportAssessment:
    return SupportAssessment(
        originalSupport=0.7,
        strongestAlternativeSupport=0.7 - margin,
        specificityMargin=margin,
        strongestAlternativeId="alt-1",
        notes=[],
    )


def _subscores() -> EvaluationSubscores:
    return EvaluationSubscores(
        rationaleSpecificity=0.8,
        actionCoupling=0.8,
        alternativeResistance=0.8,
        policyAlignment=0.8,
        contextGrounding=0.8,
    )


def test_cli_module_helpers_cover_input_shapes_empty_outputs_and_main(tmp_path: Path, capsys):
    cli_array_case = {
        "id": "cli-array",
        "domain": "sre",
        "context": "Postgres has 12 idle sessions holding locks on audit_logs.",
        "proposedAction": {"type": "terminate_idle_sessions", "target": "postgres"},
        "rationale": "Because idle sessions hold locks, terminate idle sessions.",
        "human_label": "supported",
    }
    cli_object_case = {**cli_array_case, "id": "cli-object"}
    array_path = tmp_path / "cases-array.json"
    array_path.write_text(json.dumps([cli_array_case, "ignored"]), encoding="utf-8")
    object_path = tmp_path / "cases-object.json"
    object_path.write_text(json.dumps({"cases": [cli_object_case, 42]}), encoding="utf-8")
    empty_path = tmp_path / "cases-empty.json"
    empty_path.write_text("[]", encoding="utf-8")
    invalid_path = tmp_path / "cases-invalid.json"
    invalid_path.write_text(json.dumps({"notCases": []}), encoding="utf-8")

    assert [case["id"] for case in cli._load_cases(array_path)] == ["cli-array"]
    assert [case["id"] for case in cli._load_cases(object_path)] == ["cli-object"]
    with pytest.raises(ValueError, match="JSON array"):
        cli._load_cases(invalid_path)

    fallback = cli._case_request(
        {"id": "fallback", "domain": "cloud", "context": "context long enough", "rationale": "rationale long enough", "proposedAction": "bad"}
    )
    assert fallback.domain == "generic"
    assert fallback.proposedAction.type == "invalid"

    empty_result = cli.run(empty_path, tmp_path / "empty-out")
    assert empty_result["case_count"] == 0
    assert (tmp_path / "empty-out" / "comparison.csv").read_text(encoding="utf-8") == ""

    assert cli.main([str(object_path), str(tmp_path / "main-out")]) == 0
    captured = capsys.readouterr()
    assert "cli-object" in captured.out
    assert list(csv.DictReader((tmp_path / "main-out" / "comparison.csv").open()))[0]["id"] == "cli-object"


def test_near_neighbor_generation_uses_available_actions_and_generic_fallback(monkeypatch):
    available = _request().model_copy(
        update={
            "availableActions": [
                TypedAction(type="restart service"),
                TypedAction(type="page-human"),
            ]
        }
    )
    available_alternatives = generate_near_neighbor_alternatives(available)
    available_types = [alt.action.type for alt in available_alternatives]
    assert available_types[:2] == ["restart_service", "page_human"]

    import elenchus_core.actions as actions

    monkeypatch.setattr(actions, "selected_lenses", lambda request: [])
    fallback = _request(domain="generic", action_type="custom_unknown_action")
    fallback_alternatives = generate_near_neighbor_alternatives(fallback)
    assert [alt.action.type for alt in fallback_alternatives] == ["investigate_more", "page_human", "no_action"]


def test_eval_case_loaders_and_validators_cover_error_edges(tmp_path: Path, monkeypatch):
    blank_path = tmp_path / "blank.jsonl"
    blank_path.write_text("  \n", encoding="utf-8")
    assert load_eval_cases(blank_path) == []

    array_path = tmp_path / "array.json"
    array_path.write_text(json.dumps([_case_payload("array-case")]), encoding="utf-8")
    assert load_eval_cases(array_path)[0].id == "array-case"

    jsonl_path = tmp_path / "cases.jsonl"
    jsonl_path.write_text("\n" + json.dumps(_case_payload("jsonl-case")) + "\n", encoding="utf-8")
    assert load_eval_cases(jsonl_path)[0].id == "jsonl-case"

    bad_path = tmp_path / "bad.jsonl"
    bad_path.write_text("{not-json}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid JSONL record"):
        load_eval_cases(bad_path)

    payload = _case_payload("nested-forbidden")
    payload["request"]["metadata"] = {"outer": [{"split": "smoke"}]}
    with pytest.raises(ValidationError, match="split"):
        EvalCase.model_validate(payload)

    import elenchus_core.eval_cases as eval_cases_module

    assert eval_cases_module._find_forbidden_metadata_key({"outer": [{"safe": "value"}]}) is None
    with monkeypatch.context() as patcher:
        patcher.setattr(eval_cases_module.json, "loads", lambda text: {"not": "a list"})
        with pytest.raises(ValueError, match="expected a JSON array"):
            load_eval_cases(array_path)

    invalid_label = _case_payload("invalid-label")
    invalid_label["expected"]["label"] = "invalid"
    with pytest.raises(ValidationError, match="invalid labels"):
        EvalCase.model_validate(invalid_label)

    pair_payload = _paired_payload()
    pair_payload["supported"]["expected"]["label"] = "unsupported"
    with pytest.raises(ValidationError, match="supported case"):
        PairedEvalCase.model_validate(pair_payload)

    pair_payload = _paired_payload()
    pair_payload["challenged"]["expected"]["label"] = "supported"
    with pytest.raises(ValidationError, match="challenged case"):
        PairedEvalCase.model_validate(pair_payload)

    pairs_path = tmp_path / "pairs.json"
    pairs_path.write_text(json.dumps([_paired_payload()]), encoding="utf-8")
    assert load_paired_eval_cases(pairs_path)[0].pair_id == "coverage-pair"


def test_eval_suite_metrics_and_case_failures_cover_remaining_branches(monkeypatch):
    case = _eval_case()
    report = evaluate_request(case.request)
    assert metric_value(report, "contextGrounding") == report.subscores.contextGrounding
    assert metric_value(report, "actionCoupling") == report.subscores.actionCoupling
    assert metric_value(report, "alternativeResistance") == report.subscores.alternativeResistance
    with pytest.raises(ValueError, match="unsupported ordering metric"):
        metric_value(report, "not_a_metric")

    error_report = build_error_report(case.request, "broken")
    assert metric_value(error_report, "contextGrounding") is None
    error_path_case = case.model_copy(update={"expected": case.expected.model_copy(update={"label": "error_path"})})
    assert "error_path_has_numeric_signal" in check_case(error_path_case, report)

    expected = case.expected.model_copy(
        update={
            "min_absent_anchors": 99,
            "min_present_anchors": 99,
            "min_contradicted_anchors": 99,
            "review_reasons_include": ["policy_blocker"],
            "policy_findings_include": ["missing_policy"],
        }
    )
    failures = check_case(case.model_copy(update={"expected": expected}), report)
    assert "present_anchor_floor_not_met" in failures
    assert "absent_anchor_floor_not_met" in failures
    assert "contradicted_anchor_floor_not_met" in failures
    assert "missing_review_reason:policy_blocker" in failures
    assert "missing_policy_finding:missing_policy" in failures

    expected_without_grounding = case.expected.model_copy(update={"min_absent_anchors": 1})
    assert "grounding_missing" in check_case(case.model_copy(update={"expected": expected_without_grounding}), error_report)

    contradicted_request = _request(
        trace_id="contradicted-case",
        context="CPU is normal and healthy with no CPU saturation.",
        action_type="scale_service",
        rationale="Because CPU saturation is high, scale the service.",
    )
    contradicted_report = evaluate_request(contradicted_request)
    contradicted_case = EvalCase.model_validate(
        {
            **_case_payload("contradicted-case"),
            "request": contradicted_request.model_dump(mode="json", by_alias=True, exclude_none=True),
            "expected": {"label": "supported", "maxContradictedAnchors": 0},
        }
    )
    contradicted_failures = check_case(contradicted_case, contradicted_report)
    assert "contradicted_anchor_ceiling_exceeded" in contradicted_failures
    assert "supported_case_has_contradicted_grounding" in contradicted_failures

    absent_request = _request(
        trace_id="absent-supported-case",
        context="The service has unrelated healthy telemetry and no incident markers.",
        action_type="scale_service",
        rationale="Because p99 latency is 2000ms after deploy build-123, scale the service.",
    )
    absent_report = evaluate_request(absent_request)
    absent_case = EvalCase.model_validate(
        {
            **_case_payload("absent-supported-case"),
            "request": absent_request.model_dump(mode="json", by_alias=True, exclude_none=True),
            "expected": {"label": "supported"},
        }
    )
    assert "supported_case_has_no_present_grounding" in check_case(absent_case, absent_report)

    import elenchus_core.eval_suite as suite

    base_pair = PairedEvalCase.model_validate(_paired_payload())
    supported_failed = suite.CaseOutcome(base_pair.supported, report, ["synthetic"])
    challenged_ok = suite.CaseOutcome(base_pair.challenged, report, [])
    monkeypatch.setattr(suite, "evaluate_case", lambda c: supported_failed if c.id.endswith("supported") else challenged_ok)
    assert evaluate_pair(base_pair).failure == "supported_case_failed"

    none_metric = error_report.model_copy(update={"subscores": None, "overallSignal": None})
    monkeypatch.setattr(
        suite,
        "evaluate_case",
        lambda c: suite.CaseOutcome(c, none_metric, []),
    )
    assert evaluate_pair(base_pair).failure == "metric_absent"

    low_delta_report = report.model_copy(update={"overallSignal": 0.5})
    monkeypatch.setattr(suite, "evaluate_case", lambda c: suite.CaseOutcome(c, low_delta_report, []))
    assert evaluate_pair(base_pair).failure == "pair_delta_too_small"

    counts = compute_label_counts([{"label": "unsupported", "overallSignal": None, "subscores": {}}])
    assert counts["unsupported"]["meanOverallSignal"] is None


def test_evidence_resolution_private_edges_and_empty_structured_rationale():
    ref_row, score, content = _ref_assessment(
        "artifact",
        {"artifact": EvidenceArtifact(id="artifact", type="log", content="log mentions scale service")},
        set(),
    )
    assert "pointer_missing" in ref_row.statuses
    assert score > 0
    assert content == "log mentions scale service"

    assert _action_evidence_present(_request(action_type="", target=None), "anything") is True
    assert _polarity_contradicts("no cpu pressure", "cpu pressure is high", ["no", "cpu", "pressure"]) is True
    assert _polarity_contradicts("no cpu", "cpu", ["no", "cpu"]) is False

    short_status, short_score, short_notes = _support_for_ground(
        _request(), RationaleGround(text="cpu", evidenceRefs=["a"]), ["cpu"]
    )
    assert short_status == "unresolved"
    assert short_score == 0.0
    assert "fewer than three" in short_notes[0]

    numeric_status, _, numeric_notes = _support_for_ground(
        _request(), RationaleGround(text="CPU is 95 percent high", evidenceRefs=["a"]), ["CPU is high"]
    )
    assert numeric_status == "unresolved"
    assert "numeric value" in numeric_notes[0]

    low_status, low_score, low_notes = _support_for_ground(
        _request(), RationaleGround(text="alpha beta gamma delta", evidenceRefs=["a"]), ["alpha only"]
    )
    assert low_status == "unresolved"
    assert low_score > 0
    assert "Token coverage" in low_notes[0]

    empty = assess_evidence_resolution(
        _request(
            structured={"claim": "claim", "grounds": []},
            evidence_bundle=[],
        )
    )
    assert empty.mechanicalScore == 0.0
    assert empty.supportScore == 0.0
    assert "contains no grounds" in empty.notes[-1]

    pointer_missing = assess_evidence_resolution(
        _request(
            structured={
                "claim": "claim",
                "grounds": [{"text": "log mentions terminate idle sessions", "evidenceRefs": ["a"], "loadBearing": True}],
            },
            evidence_bundle=[{"id": "a", "type": "log", "content": "log mentions terminate idle sessions"}],
        )
    )
    assert pointer_missing.summary.pointerMissing == 1


def test_grounding_private_evidence_none_and_action_entity_skip():
    assert _evidence("latency is healthy", METRIC_FAMILIES[0], "issue") is None
    assessment = assess_context_grounding(
        _request(
            context="Context has no special action token but is long enough.",
            rationale="rollback_deployment",
        )
    )
    assert assessment.summary.loadBearing == 0


def test_http_v1_invalid_path_and_healthz(monkeypatch):
    monkeypatch.delenv("ELENCHUS_API_TOKEN", raising=False)
    client = TestClient(app)
    response = client.post("/api/v1/intercept", json={"traceId": "x", "proposedAction": {"parameters": {}}})
    assert response.status_code == 200
    assert response.json() == {"score": 0, "terminalLog": ["Invalid legacy request."]}
    assert client.get("/healthz").json() == {"status": "ok"}


def test_policy_page_human_receives_high_policy_score():
    score, findings = evaluate_sre_policy(_request(action_type="page_human"))
    assert score == 0.98
    assert findings == []


def test_provider_resolution_aliases_models_errors_and_autodetect():
    assert normalize_provider_name(" Anthropic ") == "claude"
    assert normalize_provider_name("x-ai") == "grok"
    assert infer_provider_from_preferred_model("local") == "deterministic"
    assert infer_provider_from_preferred_model("claude-opus") == "claude"
    assert infer_provider_from_preferred_model("grok-3") == "grok"
    assert infer_provider_from_preferred_model("gemini-pro") == "gemini"
    assert infer_provider_from_preferred_model("custom-model") is None

    assert _model_for("claude", {}) == "claude-sonnet-4-5"
    assert _model_for("grok", {"XAI_MODEL": "grok-custom"}) == "grok-custom"
    assert _model_for("gemini", {"GEMINI_MODEL": "gemini-custom"}) == "gemini-custom"
    assert _model_for("deterministic", {}) == "heuristic-v0"
    assert _model_for("claude", {"ELENCHUS_PREFERRED_MODEL": "claude-haiku"}) == "claude-haiku"

    with pytest.raises(ValueError, match="Unsupported ELENCHUS_LLM_PROVIDER"):
        resolve_default_provider_config({"ELENCHUS_LLM_PROVIDER": "bogus"})
    with pytest.raises(ValueError, match="does not identify"):
        resolve_default_provider_config({"ELENCHUS_PREFERRED_MODEL": "custom-model"})
    with pytest.raises(ValueError, match="requires ANTHROPIC_API_KEY"):
        resolve_default_provider_config({"ELENCHUS_LLM_PROVIDER": "claude"})

    explicit = resolve_default_provider_config({"ELENCHUS_LLM_PROVIDER": "claude", "ANTHROPIC_API_KEY": "key"})
    assert explicit.provider == "claude"
    assert explicit.api_key == "key"
    autodetected = resolve_default_provider_config({"GEMINI_API_KEY": "gemini-key"})
    assert autodetected.provider == "gemini"
    assert autodetected.key_source == "GEMINI_API_KEY"
    assert resolve_default_provider_config({"API_KEY": "fallback-key"}).key_source == "API_KEY"
    assert _term_support("text", "") == 0.0


def test_report_branch_helpers_cover_caps_trust_readiness_and_weaknesses():
    assert _base_recommendation(None, []) == "abort_signal_only"
    assert _base_recommendation(0.34, []) == "escalate"
    assert _cap_recommendation("abort_signal_only", "reconsider") == "abort_signal_only"

    hard_evidence = EvidenceResolutionAssessment(
        score=0.1,
        mechanicalScore=0.1,
        supportScore=0.0,
        summary=EvidenceResolutionSummary(duplicateArtifactId=1, missingRef=1, hashMismatch=1, hashUnverifiable=1),
        refs=[],
        grounds=[],
        notes=[],
    )
    soft_evidence = EvidenceResolutionAssessment(
        score=0.5,
        mechanicalScore=0.5,
        supportScore=0.0,
        summary=EvidenceResolutionSummary(pointerMissing=1),
        refs=[],
        grounds=[],
        notes=[],
    )
    no_refs_evidence = EvidenceResolutionAssessment(
        score=0.0,
        mechanicalScore=0.0,
        supportScore=0.0,
        summary=EvidenceResolutionSummary(),
        refs=[],
        grounds=[],
        notes=[],
    )

    structured_request = _request(structured={"claim": "claim", "grounds": []})
    assert method_trust_for(structured_request, None).evidenceResolution == "missing_or_unresolved_refs"
    assert method_trust_for(structured_request, no_refs_evidence).evidenceResolution == "missing_or_unresolved_refs"
    assert recommend(0.8, [], None) == "proceed"
    assert recommend(0.8, [], _grounding(), hard_evidence) == "reconsider"
    assert recommend(0.8, [], _grounding(), soft_evidence) == "proceed_with_caveats"
    assert recommend(0.8, [PolicyFinding(code="block", severity="blocker", message="blocked")], _grounding()) == "escalate"

    reliable = support_with_margin_reliability(_support(margin=0.0))
    assert reliable.marginReliability.reason == "non_positive_margin"

    invalid_alignment = assess_project_model_alignment(
        _request(domain="tech", action_type="define_mechanism", project_model={"schemaVersion": "project-model/v0", "id": "bad", "goal": "bad", "components": []})
    )
    assert _project_model_has_alignment_gaps(invalid_alignment) is True

    weaknesses = top_weaknesses(
        _subscores(),
        _support(margin=0.1),
        [],
        _grounding(),
        hard_evidence,
    )
    assert any("duplicate artifact IDs" in item for item in weaknesses)
    assert any("Strongest near-neighbor" in item for item in weaknesses)

    ready = readiness("complete", 0.8, _grounding(), [], hard_evidence)
    assert "duplicate_evidence_artifact_id" in ready.reviewReasons
    assert "evidence_hash_unverifiable" in ready.reviewReasons

    assert confidence(_subscores(), _support(), _grounding(load_bearing=0)) > 0


def test_project_model_quality_gate_and_alignment_cover_structural_edges():
    valid = _project_model()
    assert evaluate_quality_gate(ProjectModelV0.model_validate(valid)).passed is True
    assert evaluate_quality_gate("not-a-model").findings[0].code == "schema_validation_error"

    null_source = json.loads(json.dumps(valid))
    null_source["source"]["repo"] = None
    with pytest.raises(ValidationError, match="must be omitted"):
        ProjectModelV0.model_validate(null_source)

    unsupported = json.loads(json.dumps(valid))
    unsupported["schemaVersion"] = "project-model/v9"
    unsupported_report = evaluate_quality_gate(unsupported)
    assert "unsupported_schema_version" in {finding.code for finding in unsupported_report.findings}

    invalid = _project_model(component_count=2)
    invalid["components"][0]["id"] = "stuff"
    invalid["components"][0]["name"] = "stuff"
    invalid["components"][0]["responsibilities"] = ["do things and so on"]
    invalid["components"][0]["ownedSurfaces"] = ["repo"]
    invalid["components"][0]["observableCheckIds"] = []
    invalid["components"][1]["observableCheckIds"] = ["check_event_provenance", "missing_check"]
    invalid["observableChecks"].append(
        {
            "id": "orphan_check",
            "componentId": "ghost_component",
            "mode": "inspection",
            "description": "References a missing component.",
            "observableSignal": "Missing component reference.",
            "evidenceRequired": ["audit"],
            "noLiveApi": True,
        }
    )
    invalid["dependencies"] = [
        {
            "id": "bad_dependency",
            "fromComponent": "ghost_component",
            "toComponent": "dashboard_rendering",
            "kind": "precedes",
            "description": "Unknown component should fail.",
            "observableCheckIds": [],
        }
    ]
    invalid["unclassifiedProjectSurface"] = [
        {"id": "mystery_surface", "description": "unknown", "reasonUnclassified": "unknown", "candidateOwners": []}
    ]
    invalid["risks"] = [
        {"id": "risk_dashboard", "level": "high", "description": "risk", "componentId": "dashboard_rendering"}
    ]
    codes = {finding.code for finding in evaluate_quality_gate(invalid).findings}
    assert {
        "missing_observable_check_component",
        "missing_observable_check_reference",
        "observable_check_component_mismatch",
        "component_without_observable_check",
        "vague_decomposition",
        "missing_dependency_reference",
        "unclassified_project_surface",
        "missing_held_out_probe",
    } <= codes

    missing_deps = _project_model(component_count=2)
    assert "missing_dependencies" in {finding.code for finding in evaluate_quality_gate(missing_deps).findings}

    direct_reverse = _contradictory_dependency_findings([("a", "b", "a_to_b"), ("b", "a", "b_to_a")])
    assert any(finding.code == "contradictory_dependencies" for finding in direct_reverse)
    assert _first_cycle({"a": {"b", "c"}, "b": {"c"}, "c": set()}) == []
    assert _first_cycle({"a": {"b"}, "b": {"a"}}) == ["a", "b", "a"]


def test_project_model_alignment_statuses_helpers_and_failure_hints():
    aligned_request = _request(
        domain="tech",
        action_type="define_mechanism",
        target="event_provenance",
        rationale="Ship replayable event provenance with event log evidence before dashboard rendering polish.",
        project_model=_project_model(),
    )
    aligned = assess_project_model_alignment(aligned_request)
    assert aligned.componentAlignment.status == "aligned"
    assert aligned.goalAlignment.status == "aligned"
    assert aligned.failureModeHint == "F1"

    misaligned_request = _request(
        domain="tech",
        action_type="define_mechanism",
        target="unrelated_component",
        rationale="Discuss an unrelated deployment checklist with no matching project model terms.",
        project_model=_project_model(),
    )
    misaligned = assess_project_model_alignment(misaligned_request)
    assert misaligned.componentAlignment.status == "misaligned"
    assert misaligned.goalAlignment.status == "misaligned"

    constructed = EvaluationRequest.model_construct(
        traceId="constructed-project-model",
        domain="tech",
        context="context long enough",
        proposedAction=TypedAction(type="define_mechanism"),
        rationale="rationale long enough",
        projectModel=["not", "object"],
        structuredRationale=None,
        evidenceBundle=None,
        availableActions=None,
        metadata=None,
        domainHints=[],
    )
    assert assess_project_model_alignment(constructed).projectModelValidity.status == "invalid"

    no_evidence = _request()
    assert _evidence_text(no_evidence) == ""
    assert _list_of_scalars({"not": "a list"}) == []
    assert _contains_affirmed("text", "") is False
    assert _contains_negated("text", "") is False
    assert _is_vague_component({"id": "stuff", "name": "Specific", "responsibilities": ["specific"], "ownedSurfaces": ["event log"]}) is True
    assert _is_vague_component({"id": "specific", "name": "Specific", "responsibilities": ["handle stuff"], "ownedSurfaces": ["event log"]}) is True

    feeds_model = _project_model(component_count=2)
    feeds_model["dependencies"] = [
        {
            "id": "feed_dependency",
            "fromComponent": "event_provenance",
            "toComponent": "dashboard_rendering",
            "kind": "feeds",
            "description": "Provenance feeds dashboard rendering.",
            "observableCheckIds": [],
        }
    ]
    feeds_request = _request(
        domain="tech",
        action_type="define_mechanism",
        target="dashboard_rendering",
        rationale="Use dashboard rendering from typed state.",
        project_model=feeds_model,
    )
    assert assess_project_model_alignment(feeds_request).dependencyViolations == []

    assumptions_model = _project_model()
    assumptions_model["assumptions"] = [
        {"id": "confirmed_assumption", "description": "Already proven", "status": "confirmed"},
        {"id": "hidden_assumption", "description": "Missing proof term", "status": "assumed"},
    ]
    assumption_request = _request(
        domain="tech",
        action_type="define_mechanism",
        target="event_provenance",
        rationale="Ship event provenance only.",
        project_model=assumptions_model,
    )
    assert [finding.code for finding in assess_project_model_alignment(assumption_request).unsupportedAssumptions] == [
        "unsupported_assumption"
    ]

    neighbor_model = _project_model()
    neighbor_model["nearNeighborAlternatives"] = [
        {
            "id": "dashboard_only",
            "description": "Dashboard polish only.",
            "whyNotPrimary": "It lacks provenance.",
            "distinguishingEvidence": ["replay audit"],
        },
        {
            "id": "manual_audit",
            "description": "Manual audit only.",
            "whyNotPrimary": "It lacks replay.",
            "distinguishingEvidence": ["automated replay"],
        },
    ]
    partial_neighbor_request = _request(
        domain="tech",
        action_type="define_mechanism",
        target="event_provenance",
        rationale="Rather than dashboard polish only, ship event provenance.",
        project_model=neighbor_model,
    )
    assert assess_project_model_alignment(partial_neighbor_request).nearNeighborResistance.status == "partial"

    f4_hint, f4_reason = _failure_mode_hint(
        rationale_text="some concrete rationale",
        component_alignment=misaligned.componentAlignment,
        goal_alignment=misaligned.goalAlignment,
        invariant_violations=[] ,
        dependency_violations=[],
        evidence_gaps=[],
        held_out_failures=[
            type("Finding", (), {"code": "held_out_probe_unaddressed"})(),
        ],
    )
    assert f4_hint == "F4"
    assert "project-model gaps" in f4_reason

    none_hint, none_reason = _failure_mode_hint(
        rationale_text="some concrete rationale",
        component_alignment=misaligned.componentAlignment,
        goal_alignment=misaligned.goalAlignment,
        invariant_violations=[],
        dependency_violations=[],
        evidence_gaps=[],
        held_out_failures=[],
    )
    assert none_hint is None
    assert none_reason is None
