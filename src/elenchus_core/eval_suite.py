from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .eval_cases import EvalCase, PairedEvalCase, load_eval_cases, load_paired_eval_cases, recommendation_at_most
from .evaluator import evaluate_request
from .models import EvaluationReport

OutcomeRow = dict[str, Any]


@dataclass(frozen=True)
class CaseOutcome:
    case: EvalCase
    report: EvaluationReport
    failures: list[str]


@dataclass(frozen=True)
class PairOutcome:
    pair: PairedEvalCase
    supported: CaseOutcome
    challenged: CaseOutcome
    supported_metric: float | None
    challenged_metric: float | None
    delta: float | None
    passed: bool
    failure: str | None


def metric_value(report: EvaluationReport, metric: str) -> float | None:
    if metric == "overallSignal":
        return report.overallSignal
    if report.subscores is None:
        return None
    if metric == "contextGrounding":
        return report.subscores.contextGrounding
    if metric == "actionCoupling":
        return report.subscores.actionCoupling
    if metric == "alternativeResistance":
        return report.subscores.alternativeResistance
    raise ValueError(f"unsupported ordering metric: {metric}")


def check_case(case: EvalCase, report: EvaluationReport) -> list[str]:
    failures: list[str] = []
    expected = case.expected
    if expected.require_complete and report.status != "complete":
        failures.append("status_not_complete")
    if expected.recommendation_max is not None and not recommendation_at_most(
        report.recommendation, expected.recommendation_max
    ):
        failures.append("recommendation_cap_violation")
    if expected.label == "error_path" and report.overallSignal is not None:
        failures.append("error_path_has_numeric_signal")
    if expected.label != "error_path" and report.recommendation == "abort_signal_only":
        failures.append("unexpected_abort_signal_only")
    if expected.label == "supported" and report.recommendation in {"reconsider", "escalate", "abort_signal_only"}:
        failures.append("supported_case_restrictive_recommendation")
    if report.grounding is None:
        if expected.min_absent_anchors or expected.min_present_anchors or expected.min_contradicted_anchors:
            failures.append("grounding_missing")
    else:
        if report.grounding.summary.present < expected.min_present_anchors:
            failures.append("present_anchor_floor_not_met")
        if report.grounding.summary.absent < expected.min_absent_anchors:
            failures.append("absent_anchor_floor_not_met")
        if report.grounding.summary.contradicted < expected.min_contradicted_anchors:
            failures.append("contradicted_anchor_floor_not_met")
        if (
            expected.max_contradicted_anchors is not None
            and report.grounding.summary.contradicted > expected.max_contradicted_anchors
        ):
            failures.append("contradicted_anchor_ceiling_exceeded")
        if expected.label == "supported" and report.grounding.summary.contradicted > 0:
            failures.append("supported_case_has_contradicted_grounding")
        if expected.label == "supported" and report.grounding.summary.present == 0:
            failures.append("supported_case_has_no_present_grounding")
    review_reasons = set(report.readiness.reviewReasons)
    for reason in expected.review_reasons_include:
        if reason not in review_reasons:
            failures.append(f"missing_review_reason:{reason}")
    policy_codes = {finding.code for finding in report.policyFindings}
    for code in expected.policy_findings_include:
        if code not in policy_codes:
            failures.append(f"missing_policy_finding:{code}")
    return failures


def evaluate_case(case: EvalCase) -> CaseOutcome:
    report = evaluate_request(case.request, provider=case.provider)
    return CaseOutcome(case=case, report=report, failures=check_case(case, report))


def sanitize_report_outcome(case: EvalCase, report: EvaluationReport, failures: Sequence[str]) -> OutcomeRow:
    grounding_summary: dict[str, int] | None = None
    if report.grounding is not None:
        grounding_summary = report.grounding.summary.model_dump()
    support: dict[str, float | str | None] | None = None
    if report.support is not None:
        support = {
            "originalSupport": report.support.originalSupport,
            "strongestAlternativeSupport": report.support.strongestAlternativeSupport,
            "specificityMargin": report.support.specificityMargin,
            "strongestAlternativeId": report.support.strongestAlternativeId,
        }
    subscores: dict[str, float] | None = None
    if report.subscores is not None:
        subscores = report.subscores.model_dump()
    return {
        "id": case.id,
        "split": case.split,
        "label": case.expected.label,
        "scenarioTags": case.scenario_tags,
        "sourceBenchmark": case.source.benchmark,
        "status": report.status,
        "recommendation": report.recommendation,
        "calibration": report.calibration,
        "overallSignal": report.overallSignal,
        "subscores": subscores,
        "support": support,
        "groundingSummary": grounding_summary,
        "policyFindings": [{"code": finding.code, "severity": finding.severity} for finding in report.policyFindings],
        "reviewReasons": list(report.readiness.reviewReasons),
        "operatorReviewRequired": report.readiness.operatorReviewRequired,
        "blockedUses": list(report.readiness.blockedUses),
        "passed": not failures,
        "failures": list(failures),
    }


def evaluate_pair(pair: PairedEvalCase) -> PairOutcome:
    supported = evaluate_case(pair.supported)
    challenged = evaluate_case(pair.challenged)
    supported_value = metric_value(supported.report, pair.ordering_metric)
    challenged_value = metric_value(challenged.report, pair.ordering_metric)
    failure: str | None = None
    delta: float | None = None
    if supported.failures:
        failure = "supported_case_failed"
    elif challenged.failures:
        failure = "challenged_case_failed"
    elif supported_value is None or challenged_value is None:
        failure = "metric_absent"
    else:
        delta = round(supported_value - challenged_value, 6)
        if delta < pair.min_pair_delta:
            failure = "pair_delta_too_small"
    return PairOutcome(
        pair=pair,
        supported=supported,
        challenged=challenged,
        supported_metric=supported_value,
        challenged_metric=challenged_value,
        delta=delta,
        passed=failure is None,
        failure=failure,
    )


def sanitize_pair_outcome(outcome: PairOutcome) -> OutcomeRow:
    supported_grounding = None
    if outcome.supported.report.grounding is not None:
        supported_grounding = outcome.supported.report.grounding.summary.model_dump()
    challenged_grounding = None
    if outcome.challenged.report.grounding is not None:
        challenged_grounding = outcome.challenged.report.grounding.summary.model_dump()
    return {
        "pairId": outcome.pair.pair_id,
        "metric": outcome.pair.ordering_metric,
        "supportedId": outcome.supported.case.id,
        "challengedId": outcome.challenged.case.id,
        "supportedStatus": outcome.supported.report.status,
        "challengedStatus": outcome.challenged.report.status,
        "supportedRecommendation": outcome.supported.report.recommendation,
        "challengedRecommendation": outcome.challenged.report.recommendation,
        "supportedGroundingSummary": supported_grounding,
        "challengedGroundingSummary": challenged_grounding,
        "supportedMetric": outcome.supported_metric,
        "challengedMetric": outcome.challenged_metric,
        "delta": outcome.delta,
        "requiredDelta": outcome.pair.min_pair_delta,
        "passed": outcome.passed,
        "failure": outcome.failure,
        "supportedFailures": list(outcome.supported.failures),
        "challengedFailures": list(outcome.challenged.failures),
    }


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def _row_context_grounding(row: OutcomeRow) -> float | None:
    value = row.get("contextGrounding")
    if isinstance(value, int | float):
        return float(value)
    subscores = row.get("subscores")
    if isinstance(subscores, dict):
        nested = subscores.get("contextGrounding")
        if isinstance(nested, int | float):
            return float(nested)
    return None


def _row_overall_signal(row: OutcomeRow) -> float | None:
    value = row.get("overallSignal")
    return float(value) if isinstance(value, int | float) else None


def compute_label_counts(rows: Iterable[OutcomeRow]) -> dict[str, OutcomeRow]:
    grouped: dict[str, list[OutcomeRow]] = defaultdict(list)
    for row in rows:
        label = row.get("label")
        if isinstance(label, str):
            grouped[label].append(row)
    result: dict[str, OutcomeRow] = {}
    for label, label_rows in grouped.items():
        overall_values = [value for row in label_rows if (value := _row_overall_signal(row)) is not None]
        grounding_values = [value for row in label_rows if (value := _row_context_grounding(row)) is not None]
        result[label] = {
            "count": len(label_rows),
            "passed": sum(1 for row in label_rows if row.get("passed") is True),
            "overallSignalNulls": len(label_rows) - len(overall_values),
            "contextGroundingNulls": len(label_rows) - len(grounding_values),
            "meanOverallSignal": _mean(overall_values),
            "meanContextGrounding": _mean(grounding_values),
        }
    return result


def compute_pair_ordering_accuracy(rows: Iterable[OutcomeRow]) -> float:
    pairs = list(rows)
    if not pairs:
        return 0.0
    passed = sum(1 for row in pairs if row.get("passed") is True)
    return passed / len(pairs)


def _load_optional_cases(path: Path) -> list[EvalCase]:
    return load_eval_cases(path) if path.exists() else []


def _load_optional_pairs(path: Path) -> list[PairedEvalCase]:
    return load_paired_eval_cases(path) if path.exists() else []


def run_eval_suite(input_dir: str | Path, output_dir: str | Path) -> OutcomeRow:
    cases_dir = Path(input_dir)

    cases = _load_optional_cases(cases_dir / "smoke.jsonl") + _load_optional_cases(cases_dir / "exploratory.jsonl")
    pairs = _load_optional_pairs(cases_dir / "paired_adversarial.jsonl")
    if not cases and not pairs:
        raise ValueError(
            "no eval cases or pairs found; expected smoke.jsonl, exploratory.jsonl, or paired_adversarial.jsonl"
        )

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    case_outcomes = [evaluate_case(case) for case in cases]
    pair_outcomes = [evaluate_pair(pair) for pair in pairs]
    case_rows = [sanitize_report_outcome(outcome.case, outcome.report, outcome.failures) for outcome in case_outcomes]
    pair_rows = [sanitize_pair_outcome(outcome) for outcome in pair_outcomes]
    failures = [row for row in case_rows if row["failures"]] + [row for row in pair_rows if row["failure"]]
    result: OutcomeRow = {
        "case_count": len(case_rows),
        "pair_count": len(pair_rows),
        "passed": not failures,
        "metrics": {
            "byLabel": compute_label_counts(case_rows),
            "pairOrderingAccuracy": compute_pair_ordering_accuracy(pair_rows),
        },
        "cases": case_rows,
        "pairs": pair_rows,
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "failures.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in failures), encoding="utf-8"
    )
    summary = [
        "# Elenchus Core Evaluation Suite",
        "",
        "Internal-alpha advisory signal only; not truth validation, certification, or production allow/deny.",
        "",
        f"Cases: {len(case_rows)}",
        f"Pairs: {len(pair_rows)}",
        f"Passed: {not failures}",
        f"Pair ordering accuracy: {result['metrics']['pairOrderingAccuracy']}",
    ]
    (out_dir / "summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    return result
