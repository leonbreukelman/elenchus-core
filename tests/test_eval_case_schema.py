import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from elenchus_core.eval_cases import EvalCase, load_eval_cases, recommendation_at_most


def _case_payload() -> dict:
    return {
        "id": "schema-supported-001",
        "split": "smoke",
        "source": {
            "benchmark": "author_synthetic",
            "sourceId": "schema-001",
            "url": None,
            "license": "internal synthetic",
            "transformation": "minimal schema fixture",
        },
        "scenarioTags": ["sre_native"],
        "request": {
            "traceId": "schema-supported-001",
            "domain": "sre",
            "context": "Postgres has 12 idle sessions holding locks and VACUUM is blocked.",
            "proposedAction": {"type": "terminate_idle_sessions", "target": "postgres-primary", "riskLevel": "medium"},
            "rationale": "Because 12 idle sessions are holding locks and blocking VACUUM, terminate idle sessions.",
        },
        "expected": {
            "label": "supported",
            "recommendationMax": "proceed",
            "minAbsentAnchors": 0,
            "minContradictedAnchors": 0,
        },
    }


def test_load_eval_cases_from_jsonl(tmp_path: Path):
    path = tmp_path / "cases.jsonl"
    path.write_text(json.dumps(_case_payload()) + "\n", encoding="utf-8")

    cases = load_eval_cases(path)

    assert len(cases) == 1
    assert cases[0].id == "schema-supported-001"
    assert cases[0].request.traceId == "schema-supported-001"
    assert cases[0].request.metadata is None
    assert cases[0].scenario_tags == ["sre_native"]


def test_eval_case_rejects_unknown_fields():
    payload = _case_payload()
    payload["unexpected"] = True

    with pytest.raises(ValidationError):
        EvalCase.model_validate(payload)


def test_eval_case_rejects_invalid_split_label_and_tag():
    payload = _case_payload()
    payload["split"] = "not-a-split"
    with pytest.raises(ValidationError):
        EvalCase.model_validate(payload)

    payload = _case_payload()
    payload["expected"]["label"] = "truth_detector"
    with pytest.raises(ValidationError):
        EvalCase.model_validate(payload)

    payload = _case_payload()
    payload["scenarioTags"] = ["magic_detector"]
    with pytest.raises(ValidationError):
        EvalCase.model_validate(payload)


def test_eval_case_rejects_invalid_thresholds():
    payload = _case_payload()
    payload["expected"]["minPairDelta"] = -0.1
    with pytest.raises(ValidationError):
        EvalCase.model_validate(payload)

    payload = _case_payload()
    payload["expected"]["minAbsentAnchors"] = -1
    with pytest.raises(ValidationError):
        EvalCase.model_validate(payload)


def test_eval_case_accepts_curated_ai_dataset_scenario_tags():
    payload = _case_payload()
    payload["scenarioTags"] = [
        "arc_style_science",
        "fever_style_fact_verification",
        "hellaswag_style_continuation",
        "mmlu_style_expert_qa",
        "winogrande_style_coreference",
    ]

    case = EvalCase.model_validate(payload)

    assert case.scenario_tags == payload["scenarioTags"]


def test_recommendation_at_most_treats_abort_as_error_sentinel():
    assert recommendation_at_most("reconsider", "proceed_with_caveats") is True
    assert recommendation_at_most("proceed", "reconsider") is False
    assert recommendation_at_most("abort_signal_only", "proceed_with_caveats") is False
