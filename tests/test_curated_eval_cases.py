from collections import Counter

from elenchus_core.eval_cases import load_eval_cases, recommendation_at_most
from elenchus_core.eval_suite import evaluate_case

SMOKE_PATH = "evaluation_cases/curated/smoke.jsonl"


def test_curated_smoke_cases_cover_required_behavior_and_scenario_tags():
    cases = load_eval_cases(SMOKE_PATH)
    labels = Counter(case.expected.label for case in cases)
    tags = {tag for case in cases for tag in case.scenario_tags}

    for label in {"supported", "unsupported", "contradicted", "action_mismatch", "policy_blocked"}:
        assert labels[label] >= 1

    for tag in {
        "sre_native",
        "gsm8k_style_numeric",
        "bbh_style_logic",
        "truthfulqa_style_misconception",
        "sycophancy_seed",
        "bbq_style_ambiguity",
        "numeric_absent_anchor",
        "surface_overlap_control",
    }:
        assert tag in tags


def test_curated_smoke_cases_match_expected_advisory_contracts():
    cases = load_eval_cases(SMOKE_PATH)

    for case in cases:
        outcome = evaluate_case(case)
        report = outcome.report
        assert report.calibration == "uncalibrated_internal_alpha"
        assert report.readiness.operatorReviewRequired is True
        assert "production_allow_deny" in report.readiness.blockedUses
        if case.expected.label != "error_path":
            assert report.status == "complete", case.id
            assert report.recommendation != "abort_signal_only", case.id
        if case.expected.recommendation_max:
            assert recommendation_at_most(report.recommendation, case.expected.recommendation_max), case.id
        assert outcome.failures == [], f"{case.id}: {outcome.failures}"
