from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator

from .models import ElenchusModel, EvaluationRecommendation, EvaluationRequest, EvaluationReviewReason
from .report import RECOMMENDATION_CAP_ORDER

type BehaviorLabel = Literal[
    "supported",
    "unsupported",
    "contradicted",
    "action_mismatch",
    "policy_blocked",
    "error_path",
    "invalid",
]
type SplitName = Literal["smoke", "paired", "exploratory", "lockbox"]
type ScenarioTag = Literal[
    "sre_native",
    "gsm8k_style_numeric",
    "bbh_style_logic",
    "truthfulqa_style_misconception",
    "sycophancy_seed",
    "bbq_style_ambiguity",
    "numeric_absent_anchor",
    "shuffled_context_control",
    "surface_overlap_control",
]
type OrderingMetric = Literal["overallSignal", "contextGrounding", "actionCoupling", "alternativeResistance"]


class SourceMetadata(ElenchusModel):
    benchmark: str = Field(min_length=1)
    source_id: str = Field(alias="sourceId", min_length=1)
    url: str | None = None
    license: str | None = None
    transformation: str = Field(min_length=1)


class ExpectedBehavior(ElenchusModel):
    label: BehaviorLabel
    recommendation_max: EvaluationRecommendation | None = Field(default=None, alias="recommendationMax")
    min_absent_anchors: int = Field(default=0, ge=0, alias="minAbsentAnchors")
    min_present_anchors: int = Field(default=0, ge=0, alias="minPresentAnchors")
    min_contradicted_anchors: int = Field(default=0, ge=0, alias="minContradictedAnchors")
    max_contradicted_anchors: int | None = Field(default=None, ge=0, alias="maxContradictedAnchors")
    review_reasons_include: list[EvaluationReviewReason] = Field(default_factory=list, alias="reviewReasonsInclude")
    policy_findings_include: list[str] = Field(default_factory=list, alias="policyFindingsInclude")
    require_complete: bool = Field(default=True, alias="requireComplete")
    ordering_metric: OrderingMetric | None = Field(default=None, alias="orderingMetric")
    min_pair_delta: float | None = Field(default=None, alias="minPairDelta")

    @field_validator("min_pair_delta")
    @classmethod
    def validate_min_pair_delta(cls, value: float | None) -> float | None:
        if value is not None and value < 0:
            raise ValueError("minPairDelta must be non-negative")
        return value


class EvalCase(ElenchusModel):
    id: str = Field(min_length=1)
    split: SplitName
    source: SourceMetadata
    scenario_tags: list[ScenarioTag] = Field(default_factory=list, alias="scenarioTags")
    request: EvaluationRequest
    expected: ExpectedBehavior
    provider: str = "deterministic"

    @field_validator("expected")
    @classmethod
    def validate_split_label_pairing(cls, value: ExpectedBehavior) -> ExpectedBehavior:
        if value.label == "invalid":
            raise ValueError("invalid labels are reserved for loader validation fixtures and must not be evaluated")
        return value


class PairedEvalCase(ElenchusModel):
    pair_id: str = Field(alias="pairId", min_length=1)
    split: Literal["paired"] = "paired"
    supported: EvalCase
    challenged: EvalCase
    ordering_metric: OrderingMetric = Field(default="overallSignal", alias="orderingMetric")
    min_pair_delta: float = Field(default=0.05, ge=0, alias="minPairDelta")

    @field_validator("supported")
    @classmethod
    def validate_supported_label(cls, value: EvalCase) -> EvalCase:
        if value.expected.label != "supported":
            raise ValueError("paired supported case must use expected.label=supported")
        return value

    @field_validator("challenged")
    @classmethod
    def validate_challenged_label(cls, value: EvalCase) -> EvalCase:
        if value.expected.label == "supported":
            raise ValueError("paired challenged case must not use expected.label=supported")
        return value


def _load_json_records(path: str | Path) -> list[object]:
    input_path = Path(path)
    text = input_path.read_text(encoding="utf-8")
    stripped = text.strip()
    if not stripped:
        return []
    if stripped.startswith("["):
        data = json.loads(stripped)
        if not isinstance(data, list):
            raise ValueError(f"{input_path}: expected a JSON array")
        return data
    records: list[object] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{input_path}:{line_number}: invalid JSONL record: {exc}") from exc
    return records


def load_eval_cases(path: str | Path) -> list[EvalCase]:
    return [EvalCase.model_validate(record) for record in _load_json_records(path)]


def load_paired_eval_cases(path: str | Path) -> list[PairedEvalCase]:
    return [PairedEvalCase.model_validate(record) for record in _load_json_records(path)]


def recommendation_at_most(actual: EvaluationRecommendation, cap: EvaluationRecommendation) -> bool:
    if actual not in RECOMMENDATION_CAP_ORDER or cap not in RECOMMENDATION_CAP_ORDER:
        return False
    return RECOMMENDATION_CAP_ORDER.index(actual) >= RECOMMENDATION_CAP_ORDER.index(cap)
