from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from elenchus_core.evaluator import evaluate_request
from elenchus_core.models import EvaluationRequest
from elenchus_core.project_model import assess_project_model_alignment

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs" / "schemas" / "project-model-v1.schema.json"
SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64


def _request(project_model: dict[str, Any] | None = None) -> EvaluationRequest:
    payload: dict[str, Any] = {
        "traceId": "project-model-v1-case",
        "domain": "tech",
        "context": (
            "Build Arena needs replayable event provenance before dashboard rendering polish. "
            "The project model includes event provenance, dashboard rendering, graph edge evidence, "
            "and independent held-out probes."
        ),
        "proposedAction": {
            "type": "define_mechanism",
            "target": "event_provenance",
            "riskLevel": "low",
        },
        "rationale": (
            "Because Build Arena needs replayable event provenance with graph edge evidence before "
            "dashboard rendering polish, define the event_provenance mechanism and verify it with "
            "independent held-out probes rather than shipping dashboard-only polish."
        ),
        "availableActions": [
            {"type": "define_mechanism", "target": "event_provenance", "riskLevel": "low"},
            {"type": "define_mechanism", "target": "dashboard_rendering", "riskLevel": "low"},
        ],
    }
    if project_model is not None:
        payload["projectModel"] = project_model
    return EvaluationRequest.model_validate(payload)


def _schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _assert_schema_valid(model: dict[str, Any]) -> None:
    errors = sorted(Draft202012Validator(_schema()).iter_errors(model), key=lambda error: list(error.path))
    assert errors == []


def _project_model_v1() -> dict[str, Any]:
    model = {
        "schemaVersion": "project-model/v1",
        "id": "snapshot-test-v1",
        "project": {
            "projectId": "build-arena-test",
            "projectRoot": "/tmp/build-arena-test",
            "goal": "Ship replayable event provenance before dashboard rendering polish.",
            "nonGoals": ["Do not ship dashboard-only polish."],
        },
        "snapshot": {
            "project_id": "build-arena-test",
            "project_root": "/tmp/build-arena-test",
            "goal": "Ship replayable event provenance before dashboard rendering polish.",
            "non_goals": ["Do not ship dashboard-only polish."],
            "primary_model_id": "fixture-primary-model",
            "graph_hash": SHA_A,
            "schema_version": "project-model-snapshot/v0.1",
            "snapshot_id": "snapshot-test-v1",
            "created_at_utc": "2026-06-06T00:00:00Z",
            "components": [
                {
                    "id": "event_provenance",
                    "name": "Event provenance",
                    "responsibility": "Track replayable event provenance for signal ids.",
                    "owned_node_ids": ["node_event_log"],
                    "provenance_refs": ["prov_event_log"],
                    "contract_ids": ["contract_event_dashboard"],
                    "check_ids": ["check_event_provenance"],
                    "verification_gap_ids": [],
                },
                {
                    "id": "dashboard_rendering",
                    "name": "Dashboard rendering",
                    "responsibility": "Render dashboard state from typed provenance.",
                    "owned_node_ids": ["node_dashboard"],
                    "provenance_refs": ["prov_dashboard"],
                    "contract_ids": ["contract_event_dashboard"],
                    "check_ids": ["check_dashboard_rendering"],
                    "verification_gap_ids": [],
                },
            ],
            "contracts": [
                {
                    "id": "contract_event_dashboard",
                    "name": "Event provenance feeds dashboard rendering",
                    "from_component_id": "event_provenance",
                    "to_component_id": "dashboard_rendering",
                    "supporting_edge_ids": ["edge_event_dashboard"],
                    "near_neighbor_alternative_ids": ["alternative_dashboard_only"],
                    "provenance_refs": ["prov_edge"],
                }
            ],
            "cross_cutting_concerns": [
                {
                    "id": "concern_replayability",
                    "category": "auditability",
                    "description": "Replayable provenance must survive generated summaries.",
                    "component_ids": ["event_provenance"],
                    "contract_ids": ["contract_event_dashboard"],
                    "provenance_refs": ["prov_event_log"],
                    "triggered_by": ["goal"],
                }
            ],
            "observable_checks": [
                {
                    "id": "check_event_provenance",
                    "description": "Inspect event provenance for replayable signal ids.",
                    "command": "uv run pytest tests/test_event_provenance.py -q",
                    "component_ids": ["event_provenance"],
                    "contract_ids": ["contract_event_dashboard"],
                    "provenance_refs": ["prov_event_log"],
                    "acceptance_command_id": "pytest-event-provenance",
                    "safe_to_run_by_default": True,
                    "requires_network": False,
                    "requires_paid_api": False,
                },
                {
                    "id": "check_dashboard_rendering",
                    "description": "Inspect dashboard rendering from typed state.",
                    "command": "uv run pytest tests/test_dashboard.py -q",
                    "component_ids": ["dashboard_rendering"],
                    "contract_ids": ["contract_event_dashboard"],
                    "provenance_refs": ["prov_dashboard"],
                    "acceptance_command_id": "pytest-dashboard",
                    "safe_to_run_by_default": True,
                    "requires_network": False,
                    "requires_paid_api": False,
                },
            ],
            "held_out_probes": [
                {
                    "id": "probe_event_provenance",
                    "target_component_ids": ["event_provenance"],
                    "target_contract_ids": ["contract_event_dashboard"],
                    "builder_model_id": "independent-probe-builder",
                    "builder_prompt_hash": SHA_B,
                    "builder_independent_from_decomposer": True,
                    "planted_negative_id": "negative_dashboard_only",
                    "discrimination_passed": True,
                    "golden_control_passed": True,
                    "hidden_from_primary_decomposer": True,
                    "provenance_refs": ["prov_probe"],
                }
            ],
            "verification_gaps": [
                {
                    "id": "gap_medium_readiness",
                    "description": "Medium readiness gap should remain advisory.",
                    "severity": "medium",
                    "component_ids": ["event_provenance"],
                    "contract_ids": ["contract_event_dashboard"],
                    "provenance_refs": ["prov_event_log"],
                    "proposed_closure_check": "Run the deterministic local provenance check.",
                }
            ],
            "near_neighbor_alternatives": [
                {
                    "id": "alternative_dashboard_only",
                    "target_id": "contract_event_dashboard",
                    "alternative": "Ship dashboard rendering polish without provenance.",
                    "why_not_primary": "It lacks replayable event provenance.",
                    "provenance_refs": ["prov_dashboard"],
                }
            ],
            "acceptance_command_allowlist": [
                "uv run pytest tests/test_event_provenance.py -q",
                "uv run pytest tests/test_dashboard.py -q",
            ],
            "prompt_hashes": {"decomposer": SHA_B},
            "model_output_hashes": {"snapshot": SHA_C},
            "input_hashes": {"graph": SHA_A},
        },
        "projectGraph": {
            "schemaVersion": "project-graph/v0",
            "graphHash": SHA_A,
            "projectRoot": "/tmp/build-arena-test",
            "nodes": [
                {
                    "id": "node_event_log",
                    "kind": "source",
                    "label": "event log",
                    "path": "src/events.py",
                    "symbol": "EventLog",
                    "tags": ["provenance"],
                    "provenance_refs": [
                        {
                            "id": "prov_event_log",
                            "source_type": "file",
                            "derived_by": "project_graph",
                            "confidence": "high",
                            "content_hash": SHA_A,
                            "path": "src/events.py",
                            "line_start": 1,
                            "line_end": 20,
                            "git_oid": SHA_D,
                            "dirty": False,
                        }
                    ],
                },
                {
                    "id": "node_dashboard",
                    "kind": "source",
                    "label": "dashboard",
                    "path": "src/dashboard.py",
                    "symbol": "Dashboard",
                    "tags": ["ui"],
                    "provenance_refs": [
                        {
                            "id": "prov_dashboard",
                            "source_type": "file",
                            "derived_by": "project_graph",
                            "confidence": "high",
                            "content_hash": SHA_B,
                            "path": "src/dashboard.py",
                            "line_start": 1,
                            "line_end": 12,
                            "git_oid": SHA_D,
                            "dirty": False,
                        }
                    ],
                },
            ],
            "edges": [
                {
                    "id": "edge_event_dashboard",
                    "kind": "feeds",
                    "from_node_id": "node_event_log",
                    "to_node_id": "node_dashboard",
                    "label": "event provenance feeds dashboard rendering",
                    "provenance_refs": [
                        {
                            "id": "prov_edge",
                            "source_type": "static-analysis",
                            "derived_by": "project_graph",
                            "confidence": "medium",
                            "content_hash": SHA_C,
                            "path": "src/dashboard.py",
                            "line_start": 4,
                            "line_end": 8,
                            "git_oid": SHA_D,
                            "dirty": False,
                        },
                        {
                            "id": "prov_probe",
                            "source_type": "fixture",
                            "derived_by": "held_out_probe_builder",
                            "confidence": "medium",
                            "content_hash": SHA_D,
                            "path": "tests/test_event_provenance.py",
                            "line_start": 1,
                            "line_end": 5,
                            "git_oid": SHA_D,
                            "dirty": False,
                        },
                    ],
                    "confidence": "medium",
                    "derived_by": "project_graph",
                }
            ],
        },
        "gateReport": {"passed": True, "violations": []},
        "provenance": {
            "git": {
                "available": True,
                "root": "/tmp/build-arena-test",
                "headOid": SHA_D,
                "dirty": False,
                "dirtyPaths": [],
                "dirtyStateFingerprint": SHA_C,
            },
            "provenanceRefStrategy": (
                "All graph, component, contract, check, probe, and gap claims must resolve to ProjectGraph ProvenanceRef ids."
            ),
        },
        "hashes": {
            "inputHashes": {"graph": SHA_A},
            "promptHashes": {"decomposer": SHA_B},
            "outputHashes": {"snapshot": SHA_C},
            "artifactHashes": {"project-model-v1.json": SHA_D},
        },
        "models": {"primary": "fixture-primary-model", "probeBuilders": ["independent-probe-builder"]},
        "derivedArtifacts": [
            {"artifactType": "jsonl-events", "path": "events.jsonl", "strategy": "Canonical future run-loop events."},
            {"artifactType": "sqlite-projection", "path": "events.sqlite", "strategy": "Query-only derived state."},
            {"artifactType": "markdown-summary", "path": "summary.md", "strategy": "Generated human-readable view."},
        ],
        "compatibility": {
            "projectModelV0Path": "project-model-v0.json",
            "projectModelV0Role": "legacy compatibility projection",
        },
    }
    _assert_schema_valid(model)
    return model


def _mutated_v1() -> dict[str, Any]:
    return copy.deepcopy(_project_model_v1())


def _finding_codes(findings: list[Any]) -> set[str]:
    return {finding.code for finding in findings}


def test_project_model_v1_fixture_matches_vendored_build_arena_schema_snapshot() -> None:
    _assert_schema_valid(_project_model_v1())


def test_project_model_v1_is_accepted_not_unsupported_and_does_not_overgate_clean_model() -> None:
    clean_report = evaluate_request(_request(_project_model_v1()))
    no_model_report = evaluate_request(_request())

    assert clean_report.status == "complete"
    assert clean_report.projectModelAlignment.projectModelValidity.status == "valid"
    assert clean_report.projectModelAlignment.projectModelValidity.schemaVersion == "project-model/v1"
    assert clean_report.projectModelAlignment.projectModelValidity.qualityGatePassed is True
    assert "invalid_project_model" not in clean_report.readiness.reviewReasons
    assert "project_model_alignment_gap" not in clean_report.readiness.reviewReasons
    assert clean_report.recommendation == no_model_report.recommendation


def test_unknown_project_model_schema_version_still_reports_unsupported_version() -> None:
    model = _mutated_v1()
    model["schemaVersion"] = "project-model/v9"

    alignment = assess_project_model_alignment(_request(model))

    assert alignment.projectModelValidity.status == "unsupported_version"
    assert "unsupported_schema_version" in _finding_codes(alignment.projectModelValidity.findings)


def test_project_model_v1_provenance_gaps_are_reported() -> None:
    model = _mutated_v1()
    model["projectGraph"]["nodes"][0]["provenance_refs"] = []
    model["snapshot"]["components"][0]["provenance_refs"] = ["fabricated_prov_ref"]

    alignment = assess_project_model_alignment(_request(model))

    assert alignment.projectModelValidity.status == "valid"
    assert {"missing_project_graph_provenance", "unknown_project_model_provenance_ref"} <= _finding_codes(
        alignment.evidenceGroundingGaps
    )


def test_project_model_v1_gate_failure_caps_recommendation_and_keeps_specific_finding() -> None:
    model = _mutated_v1()
    model["gateReport"] = {
        "passed": False,
        "violations": [
            {
                "gate": "provenance_refs_resolve",
                "severity": "error",
                "message": "A component has fabricated provenance.",
                "location": "snapshot.components[event_provenance].provenance_refs",
            }
        ],
    }
    _assert_schema_valid(model)

    report = evaluate_request(_request(model))

    assert report.projectModelAlignment.projectModelValidity.schemaVersion == "project-model/v1"
    assert report.projectModelAlignment.projectModelValidity.qualityGatePassed is False
    assert "project_model_v1_gate_failed" in _finding_codes(report.projectModelAlignment.projectModelValidity.findings)
    assert report.recommendation not in {"proceed", "proceed_with_caveats"}
    assert "invalid_project_model" in report.readiness.reviewReasons
    assert any("Project Model" in weakness for weakness in report.topWeaknesses)


def test_project_model_v1_held_out_probe_and_high_verification_gaps_are_review_gaps() -> None:
    model = _mutated_v1()
    model["snapshot"]["held_out_probes"][0]["builder_independent_from_decomposer"] = False
    model["snapshot"]["held_out_probes"][0]["discrimination_passed"] = False
    model["snapshot"]["verification_gaps"].append(
        {
            "id": "gap_blocking_provenance",
            "description": "No deterministic closure check proves provenance survives summary generation.",
            "severity": "blocker",
            "component_ids": ["event_provenance"],
            "contract_ids": ["contract_event_dashboard"],
            "provenance_refs": ["prov_event_log"],
            "proposed_closure_check": "Add a deterministic summary provenance regression test.",
        }
    )
    _assert_schema_valid(model)

    report = evaluate_request(_request(model))

    assert {"held_out_probe_not_independent", "held_out_probe_failed"} <= _finding_codes(
        report.projectModelAlignment.heldOutProbeFailures
    )
    assert "high_or_blocker_verification_gap" in _finding_codes(report.projectModelAlignment.evidenceGroundingGaps)
    assert "project_model_alignment_gap" in report.readiness.reviewReasons
    assert any("verification gap" in weakness.lower() or "project model" in weakness.lower() for weakness in report.topWeaknesses)


def test_project_model_v1_absent_held_out_probes_are_advisory_gap() -> None:
    model = _mutated_v1()
    model["snapshot"]["held_out_probes"] = []

    alignment = assess_project_model_alignment(_request(model))

    assert "missing_held_out_probe" in _finding_codes(alignment.heldOutProbeFailures)


def test_project_model_v1_observable_checks_are_evaluated_as_advisory_surface() -> None:
    model = _mutated_v1()
    model["snapshot"]["observable_checks"][0]["command"] = "uv run pytest tests/test_unallowlisted_live_probe.py -q"
    model["snapshot"]["observable_checks"][0]["safe_to_run_by_default"] = False
    model["snapshot"]["observable_checks"][0]["requires_network"] = True
    model["snapshot"]["observable_checks"][0]["requires_paid_api"] = True
    _assert_schema_valid(model)

    alignment = assess_project_model_alignment(_request(model))

    assert {
        "observable_check_not_allowlisted",
        "observable_check_not_safe_by_default",
        "observable_check_requires_network",
        "observable_check_requires_paid_api",
    } <= _finding_codes(alignment.evidenceGroundingGaps)


def test_project_model_v1_malformed_required_shape_is_invalid_not_unsupported() -> None:
    model = _mutated_v1()
    del model["provenance"]["git"]["dirtyStateFingerprint"]

    alignment = assess_project_model_alignment(_request(model))

    assert alignment.projectModelValidity.status == "invalid"
    assert alignment.projectModelValidity.schemaVersion == "project-model/v1"
    assert "missing_dirty_state_fingerprint" in _finding_codes(alignment.projectModelValidity.findings)


def test_project_model_v1_invalid_dirty_state_fingerprint_shape_is_invalid() -> None:
    model = _mutated_v1()
    model["provenance"]["git"]["dirtyStateFingerprint"] = "not-a-sha256"

    alignment = assess_project_model_alignment(_request(model))

    assert alignment.projectModelValidity.status == "invalid"
    assert "invalid_dirty_state_fingerprint" in _finding_codes(alignment.projectModelValidity.findings)


def test_project_model_v1_missing_gate_passed_is_invalid_not_clean_pass() -> None:
    model = _mutated_v1()
    del model["gateReport"]["passed"]

    alignment = assess_project_model_alignment(_request(model))

    assert alignment.projectModelValidity.status == "invalid"
    assert alignment.projectModelValidity.qualityGatePassed is False
    assert "invalid_project_model_v1_gate_report" in _finding_codes(alignment.projectModelValidity.findings)


def test_project_model_v1_dirty_tree_warning_requires_valid_fingerprint() -> None:
    model = _mutated_v1()
    model["provenance"]["git"]["dirty"] = True
    model["provenance"]["git"]["dirtyPaths"] = ["src/events.py"]
    _assert_schema_valid(model)

    alignment = assess_project_model_alignment(_request(model))

    assert alignment.projectModelValidity.status == "valid"
    assert "dirty_project_model_provenance" in _finding_codes(alignment.evidenceGroundingGaps)


def test_project_model_v1_medium_verification_gap_and_absent_near_neighbors_do_not_create_error_gap() -> None:
    model = _mutated_v1()
    model["snapshot"]["near_neighbor_alternatives"] = []
    model["snapshot"]["contracts"][0]["near_neighbor_alternative_ids"] = []
    _assert_schema_valid(model)

    alignment = assess_project_model_alignment(_request(model))

    assert alignment.nearNeighborResistance.status == "not_available"
    assert "high_or_blocker_verification_gap" not in _finding_codes(alignment.evidenceGroundingGaps)
