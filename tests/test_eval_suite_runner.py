import json
from pathlib import Path

import pytest

from elenchus_core.eval_cases import EvalCase, PairedEvalCase
from elenchus_core.eval_suite import (
    compute_label_counts,
    compute_pair_ordering_accuracy,
    evaluate_case,
    evaluate_pair,
    run_eval_suite,
    sanitize_pair_outcome,
    sanitize_report_outcome,
)
from elenchus_core.evaluator import evaluate_request


def _sentinel_case() -> EvalCase:
    return EvalCase.model_validate(
        {
            "id": "sentinel-supported-001",
            "split": "smoke",
            "source": {
                "benchmark": "author_synthetic",
                "sourceId": "sentinel-001",
                "url": None,
                "license": "internal synthetic",
                "transformation": "sanitization sentinel fixture",
            },
            "scenarioTags": ["sre_native"],
            "request": {
                "traceId": "sentinel-supported-001",
                "domain": "sre",
                "context": "Postgres has 12 idle sessions holding locks. CTX_SENTINEL_DO_NOT_LEAK_7319 RAT_SENTINEL_DO_NOT_LEAK_7319",
                "proposedAction": {
                    "type": "terminate_idle_sessions",
                    "target": "postgres-primary",
                    "riskLevel": "medium",
                },
                "rationale": "Because 12 idle sessions are holding locks, terminate idle sessions. CTX_SENTINEL_DO_NOT_LEAK_7319 RAT_SENTINEL_DO_NOT_LEAK_7319",
            },
            "expected": {"label": "supported", "recommendationMax": "proceed"},
        }
    )


def test_sanitized_outcome_is_allowlisted_and_omits_raw_prose():
    case = _sentinel_case()
    report = evaluate_request(case.request)

    outcome = sanitize_report_outcome(case, report, failures=[])
    rendered = repr(outcome)

    assert "CTX_SENTINEL_DO_NOT_LEAK_7319" not in rendered
    assert "RAT_SENTINEL_DO_NOT_LEAK_7319" not in rendered
    assert "contextEvidence" not in rendered
    assert "contradictionEvidence" not in rendered
    assert "toulmin" not in rendered
    assert "anchors" not in rendered
    assert set(outcome) <= {
        "id",
        "split",
        "label",
        "scenarioTags",
        "sourceBenchmark",
        "status",
        "recommendation",
        "calibration",
        "overallSignal",
        "subscores",
        "support",
        "groundingSummary",
        "evidenceResolution",
        "methodTrust",
        "policyFindings",
        "reviewReasons",
        "operatorReviewRequired",
        "blockedUses",
        "passed",
        "failures",
    }


def test_v2_sanitized_outcome_includes_evidence_summary_without_raw_artifact_content():
    case_payload = _sentinel_case().model_dump(by_alias=True)
    case_payload["id"] = "sentinel-v2-evidence-001"
    case_payload["request"]["traceId"] = "sentinel-v2-evidence-001"
    case_payload["request"]["domain"] = "security"
    case_payload["request"]["context"] = "CI log mentions a token exposure; CTX_SENTINEL_DO_NOT_LEAK_7319."
    case_payload["request"]["proposedAction"] = {"type": "revoke_token", "target": "github-token"}
    case_payload["request"]["rationale"] = "Because CI log shows token exposure, revoke the token. RAT_SENTINEL_DO_NOT_LEAK_7319"
    case_payload["request"]["structuredRationale"] = {
        "claim": "Revoke the exposed token.",
        "grounds": [
            {
                "text": "CI log shows token exposure.",
                "evidenceRefs": ["ci-log"],
                "loadBearing": True,
            }
        ],
    }
    case_payload["request"]["evidenceBundle"] = [
        {
            "id": "ci-log",
            "type": "ci_log",
            "contentPointer": "ci://build/log#L1",
            "content": "ARTIFACT_SENTINEL_DO_NOT_LEAK_7319 CI log shows token exposure for github-token.",
        }
    ]
    case = EvalCase.model_validate(case_payload)
    report = evaluate_request(case.request)

    outcome = sanitize_report_outcome(case, report, failures=[])
    rendered = repr(outcome)

    assert outcome["evidenceResolution"] is not None
    assert outcome["methodTrust"] is not None
    assert "ARTIFACT_SENTINEL_DO_NOT_LEAK_7319" not in rendered
    assert "CI log shows token exposure for github-token" not in rendered
    assert "ci-log" in rendered


def test_non_complete_ordinary_case_is_failure_but_error_path_keeps_null_signal():
    ordinary = _sentinel_case()
    ordinary = ordinary.model_copy(update={"provider": "broken"})
    ordinary_outcome = evaluate_case(ordinary)

    assert ordinary_outcome.report.status == "error"
    assert "status_not_complete" in ordinary_outcome.failures
    assert "recommendation_cap_violation" in ordinary_outcome.failures

    expected = ordinary.expected.model_copy(update={"label": "error_path", "require_complete": False})
    error_case = ordinary.model_copy(update={"expected": expected})
    error_outcome = evaluate_case(error_case)

    assert error_outcome.report.recommendation == "abort_signal_only"
    assert error_outcome.report.overallSignal is None
    assert "status_not_complete" not in error_outcome.failures


def test_metric_helpers_are_null_safe():
    rows = [
        {"label": "supported", "overallSignal": 0.8, "contextGrounding": 0.9},
        {"label": "supported", "overallSignal": None, "contextGrounding": None},
        {"label": "contradicted", "overallSignal": 0.3, "contextGrounding": 0.2},
    ]

    counts = compute_label_counts(rows)

    assert counts["supported"]["count"] == 2
    assert counts["supported"]["overallSignalNulls"] == 1
    assert counts["supported"]["meanOverallSignal"] == 0.8
    assert counts["contradicted"]["meanContextGrounding"] == 0.2


def test_pair_ordering_accuracy_counts_ties_and_nulls_as_failures():
    pairs = [
        {"pairId": "pass", "passed": True},
        {"pairId": "fail", "passed": False},
        {"pairId": "null", "passed": False},
    ]

    assert compute_pair_ordering_accuracy(pairs) == 1 / 3


def test_sanitized_pair_outcome_includes_underlying_case_failures():
    supported_payload = _sentinel_case().model_dump(by_alias=True)
    supported_payload["id"] = "pair-failure-supported"
    supported_payload["split"] = "paired"
    supported_payload["request"]["traceId"] = "pair-failure-supported"

    challenged_payload = json.loads(json.dumps(supported_payload))
    challenged_payload["id"] = "pair-failure-challenged"
    challenged_payload["request"]["traceId"] = "pair-failure-challenged"
    challenged_payload["expected"]["label"] = "unsupported"
    challenged_payload["expected"]["minPresentAnchors"] = 999

    pair = PairedEvalCase.model_validate(
        {
            "pairId": "pair-failure-row",
            "supported": supported_payload,
            "challenged": challenged_payload,
        }
    )

    outcome = evaluate_pair(pair)
    row = sanitize_pair_outcome(outcome)

    assert row["failure"] == "challenged_case_failed"
    assert row["supportedFailures"] == []
    assert "present_anchor_floor_not_met" in row["challengedFailures"]


def test_runner_outputs_do_not_leak_sentinel_tokens(tmp_path: Path):
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    case = _sentinel_case()
    (cases_dir / "smoke.jsonl").write_text(case.model_dump_json(by_alias=True) + "\n", encoding="utf-8")
    output_dir = tmp_path / "benchmark-output" / "eval-suite"

    result = run_eval_suite(cases_dir, output_dir)

    assert result["case_count"] == 1
    for name in ["result.json", "summary.md", "failures.jsonl"]:
        text = (output_dir / name).read_text(encoding="utf-8")
        assert "CTX_SENTINEL_DO_NOT_LEAK_7319" not in text
        assert "RAT_SENTINEL_DO_NOT_LEAK_7319" not in text


def test_runner_rejects_empty_suite_without_success_artifacts(tmp_path: Path):
    cases_dir = tmp_path / "empty-cases"
    cases_dir.mkdir()
    output_dir = tmp_path / "benchmark-output" / "eval-suite"

    with pytest.raises(ValueError, match="no eval cases or pairs"):
        run_eval_suite(cases_dir, output_dir)

    assert not (output_dir / "result.json").exists()
    assert not (output_dir / "summary.md").exists()


def test_cli_help_mentions_all_loaded_input_files():
    cli = Path("scripts/run_eval_suite.py").read_text(encoding="utf-8")
    assert "smoke.jsonl" in cli
    assert "exploratory.jsonl" in cli
    assert "paired_adversarial.jsonl" in cli


def test_repo_benchmark_output_directory_is_ignored():
    gitignore = Path(".gitignore").read_text(encoding="utf-8")
    assert "benchmark-output/" in gitignore
