from __future__ import annotations

import re
from dataclasses import dataclass
from typing import cast

from .models import (
    ContextGroundingAssessment,
    ContextGroundingSummary,
    EvaluationRequest,
    GroundingAnchor,
    GroundingAnchorKind,
    GroundingAnchorStatus,
)

ANCHOR_WEIGHTS = {"numeric": 1.0, "entity": 0.7, "metric_state": 1.2, "mechanism": 1.2}
GROUNDING_RULESET_FINGERPRINT = "grounding-py-alpha-2026-06-01"
RECOMMENDATION_GROUNDING_FLOORS = {
    "contradictionCap": "reconsider",
    "lowGroundingThreshold": 0.4,
    "lowGroundingCap": "reconsider",
    "mediumGroundingThreshold": 0.6,
    "mediumGroundingCap": "proceed_with_caveats",
}
GROUNDING_SCORE_CAPS = {
    "noAnchorFloor": 0.45,
    "anchorlessContextCap": 0.25,
    "contradictedHighWeightCap": 0.35,
    "absentHalfWeightCap": 0.5,
    "absentHighWeightMechanismCap": 0.65,
}
LOW_GROUNDING_THRESHOLD = 0.4
MEDIUM_GROUNDING_THRESHOLD = 0.6

NUMERIC_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:%|ms|s|sec|secs|seconds?|m|min|mins|minutes?|h|hr|hrs|hours?|days?|x|mb|gb|iops)?\b", re.I
)
ENTITY_RE = re.compile(r"\b[a-z][a-z0-9]+(?:[-_][a-z0-9]+)+\b", re.I)


@dataclass(frozen=True)
class Family:
    name: str
    terms: tuple[re.Pattern[str], ...]
    issue: tuple[re.Pattern[str], ...]
    normal: tuple[re.Pattern[str], ...]


def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.I)


METRIC_FAMILIES: tuple[Family, ...] = (
    Family(
        "latency",
        (_rx(r"\bp\d+\s+latency\b"), _rx(r"\blatency\b"), _rx(r"\bresponse\s+time\b")),
        (
            _rx(r"\b(rose|rising|increased?|elevated|high|slow|degraded|regression|spike|spiking)\b"),
            _rx(r"\b\d+(?:\.\d+)?\s*ms\b"),
        ),
        (_rx(r"\b(normal|steady|baseline|unchanged|healthy|nominal|low)\b"),),
    ),
    Family(
        "errors",
        (_rx(r"\b5xx\b"), _rx(r"\berror\s+rate\b"), _rx(r"\berrors?\b")),
        (
            _rx(r"\b(rose|rising|increased?|elevated|high|degraded|regression|spike|spiking|affects?)\b"),
            _rx(r"\b\d+(?:\.\d+)?\s*%\b"),
        ),
        (_rx(r"\b(normal|steady|baseline|unchanged|healthy|nominal|low)\b"),),
    ),
    Family(
        "cpu",
        (_rx(r"\bcpu\b"), _rx(r"\bprocessor\b")),
        (
            _rx(r"\b(saturation|saturated|pressure|contention|high|elevated|hot|pegged)\b"),
            _rx(r"\b\d+(?:\.\d+)?\s*%\b"),
        ),
        (_rx(r"\b(normal|healthy|idle|low|nominal|absent|no\s+cpu\s+saturation)\b"),),
    ),
    Family(
        "memory",
        (_rx(r"\bmemory\b"), _rx(r"\bheap\b"), _rx(r"\boom\b")),
        (
            _rx(r"\b(leak|pressure|exhaustion|grows?|growth|saturation|high|elevated|oom)\b"),
            _rx(r"\b\d+(?:\.\d+)?\s*(?:mb|gb)\b"),
        ),
        (_rx(r"\b(normal|healthy|steady|baseline|absent|no\s+memory\s+pressure|no\s+memory\s+leak)\b"),),
    ),
    Family(
        "io",
        (
            _rx(r"\bi/o\b"),
            _rx(r"\bio\s+wait\b"),
            _rx(r"\biowait\b"),
            _rx(r"\biops\b"),
            _rx(r"\bdisk\b"),
            _rx(r"\bstorage\b"),
        ),
        (
            _rx(r"\b(wait|saturation|saturated|bottleneck|high|elevated|exhausted|pressure|spike|spiking)\b"),
            _rx(r"\b\d+(?:\.\d+)?\s*(?:%|iops)\b"),
        ),
        (_rx(r"\b(normal|healthy|steady|baseline|unchanged|low|nominal)\b"),),
    ),
    Family(
        "locks",
        (_rx(r"\blocks?\b"), _rx(r"\block\s+waits?\b"), _rx(r"\bidle\s+in\s+transaction\b"), _rx(r"\bvacuum\b")),
        (
            _rx(r"\b(blocking|blocked|holding|waits?|contention|older\s+than)\b"),
            _rx(r"\b\d+(?:\.\d+)?\s*(?:m|min|mins|minutes?|h|hours?)?\b"),
        ),
        (_rx(r"\b(no\s+locks?|no\s+lock\s+waits?|not\s+blocked|clear|healthy|normal)\b"),),
    ),
    Family(
        "release",
        (_rx(r"\bdeploy(?:ment)?\b"), _rx(r"\brelease\b"), _rx(r"\brollout\b"), _rx(r"\bversion\b"), _rx(r"\bbuild\b")),
        (_rx(r"\b(after|latest|caused?|correlated|correlation|regression|change)\b"),),
        (
            _rx(
                r"\b(no\s+(?:deploy|deployment|release|rollout|version|version\s+change)|quiet|empty|not\s+correlated|unrelated)\b"
            ),
        ),
    ),
)

MECHANISM_FAMILIES: tuple[Family, ...] = (
    Family(
        "release_correlation",
        (_rx(r"\bdeploy(?:ment)?\b"), _rx(r"\brelease\b"), _rx(r"\bversion\b"), _rx(r"\bregression\b")),
        (
            _rx(r"\bafter\s+(?:the\s+)?(?:latest\s+)?(?:deploy|deployment|release|rollout)\b"),
            _rx(r"\b(?:deploy|deployment|release|rollout|version)\s+(?:caused?|introduced|triggered)\b"),
            _rx(r"\blatest\s+(?:deployment|deploy|release|version)\b"),
            _rx(r"\bregression\b"),
        ),
        (
            _rx(r"\bno\s+(?:deploy|deployment|release|rollout|version\s+change|version)\b"),
            _rx(r"\bnot\s+(?:deploy|deployment|release|rollout)[-\s]?correlated\b"),
        ),
    ),
    Family(
        "resource_contention",
        (
            _rx(r"\bresource\b"),
            _rx(r"\bcpu\b"),
            _rx(r"\bmemory\b"),
            _rx(r"\bi/o\b"),
            _rx(r"\bdisk\b"),
            _rx(r"\bcapacity\b"),
        ),
        (
            _rx(r"\bresource\s+contention\b"),
            _rx(
                r"\b(?:cpu|memory|i/o|io|disk|storage|capacity)\s+(?:saturation|pressure|contention|bottleneck|exhaustion)\b"
            ),
        ),
        (
            _rx(r"\bno\s+resource\s+saturation\b"),
            _rx(r"\b(?:cpu|memory|i/o|io|disk|storage|capacity)\s+(?:is\s+)?(?:normal|healthy|nominal|steady|low)\b"),
        ),
    ),
    Family(
        "lock_contention",
        (_rx(r"\block"), _rx(r"\bidle\s+in\s+transaction\b"), _rx(r"\bvacuum\b")),
        (
            _rx(r"\bidle\s+in\s+transaction\b"),
            _rx(r"\bholding\s+locks?\b"),
            _rx(r"\bblocking\s+vacuum\b"),
            _rx(r"\bvacuum\s+is\s+blocked\b"),
            _rx(r"\block\s+waits?\b"),
        ),
        (
            _rx(r"\bno\s+locks?\b"),
            _rx(r"\bno\s+lock\s+waits?\b"),
            _rx(r"\bvacuum\s+(?:is\s+)?not\s+blocked\b"),
            _rx(r"\bno\s+idle\s+in\s+transaction\b"),
        ),
    ),
)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9%._/\-]+", " ", text.lower())).strip()


def _has_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _evidence(text: str, family: Family, polarity: str) -> str | None:
    patterns = family.issue if polarity == "issue" else family.normal
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return None


def _family_polarity(text: str, family: Family) -> str | None:
    if not _has_any(text, family.terms):
        return None
    issue = _has_any(text, family.issue)
    normal = _has_any(text, family.normal)
    if issue and not normal:
        return "issue"
    if normal and not issue:
        return "normal"
    if issue and normal:
        return "normal" if re.search(r"\b(no|not|normal|healthy|absent|unchanged)\b", text, re.I) else "issue"
    return None


def _status_for_family(context: str, family: Family, polarity: str) -> tuple[str, str | None, str | None]:
    context_polarity = _family_polarity(context, family)
    if context_polarity == polarity:
        return "present", _evidence(context, family, polarity), None
    if context_polarity and context_polarity != polarity:
        return "contradicted", None, _evidence(context, family, context_polarity)
    return "absent", None, None


def _anchor(
    anchor_id: int, kind: str, text: str, status: str, evidence: str | None, contradiction: str | None, notes: list[str]
) -> GroundingAnchor:
    typed_kind = cast(GroundingAnchorKind, kind)
    typed_status = cast(GroundingAnchorStatus, status)
    return GroundingAnchor(
        id=f"anchor-{anchor_id}",
        kind=typed_kind,
        text=text,
        normalizedText=normalize_text(text),
        loadBearing=True,
        status=typed_status,
        contextEvidence=evidence,
        contradictionEvidence=contradiction,
        weight=ANCHOR_WEIGHTS[kind],
        notes=notes,
    )


def assess_context_grounding(request: EvaluationRequest) -> ContextGroundingAssessment:
    rationale = request.rationale
    context = request.context
    anchors: list[GroundingAnchor] = []
    next_id = 1

    for token in sorted(set(NUMERIC_RE.findall(rationale)), key=lambda item: rationale.find(item)):
        status = "present" if normalize_text(token) in normalize_text(context) else "absent"
        anchors.append(
            _anchor(
                next_id,
                "numeric",
                token,
                status,
                token if status == "present" else None,
                None,
                ["numeric threshold match"],
            )
        )
        next_id += 1

    for token in sorted(set(ENTITY_RE.findall(rationale)), key=lambda item: rationale.find(item)):
        if token in {"rollback_deployment", "terminate_idle_sessions", "scale_service", "restart_service"}:
            continue
        status = "present" if normalize_text(token) in normalize_text(context) else "absent"
        anchors.append(
            _anchor(
                next_id, "entity", token, status, token if status == "present" else None, None, ["entity literal match"]
            )
        )
        next_id += 1

    for family in METRIC_FAMILIES:
        polarity = _family_polarity(rationale, family)
        if polarity is None:
            continue
        status, evidence, contradiction = _status_for_family(context, family, polarity)
        anchors.append(
            _anchor(
                next_id,
                "metric_state",
                f"{family.name}:{polarity}",
                status,
                evidence,
                contradiction,
                [f"metric family {family.name}"],
            )
        )
        next_id += 1

    for family in MECHANISM_FAMILIES:
        polarity = _family_polarity(rationale, family)
        if polarity is None:
            continue
        status, evidence, contradiction = _status_for_family(context, family, polarity)
        anchors.append(
            _anchor(
                next_id,
                "mechanism",
                f"{family.name}:{polarity}",
                status,
                evidence,
                contradiction,
                [f"mechanism family {family.name}"],
            )
        )
        next_id += 1

    if not anchors:
        return ContextGroundingAssessment(
            score=GROUNDING_SCORE_CAPS["anchorlessContextCap"],
            anchors=[],
            summary=ContextGroundingSummary(present=0, absent=0, contradicted=0, loadBearing=0),
            notes=[
                "No load-bearing anchors were extracted; fallback grounding cannot justify permissive recommendations.",
                "Deterministic context-grounding proxy over supplied context only; not objective truth validation.",
            ],
        )

    total = sum(anchor.weight for anchor in anchors if anchor.loadBearing)
    present = sum(anchor.weight for anchor in anchors if anchor.status == "present" and anchor.loadBearing)
    contradicted = sum(1 for anchor in anchors if anchor.status == "contradicted")
    absent = sum(1 for anchor in anchors if anchor.status == "absent")
    score = round(present / total if total else GROUNDING_SCORE_CAPS["noAnchorFloor"], 4)
    if contradicted:
        score = min(score, GROUNDING_SCORE_CAPS["contradictedHighWeightCap"])
    elif absent >= max(1, len(anchors) // 2):
        score = min(score, GROUNDING_SCORE_CAPS["absentHalfWeightCap"])
    return ContextGroundingAssessment(
        score=round(score, 4),
        anchors=anchors,
        summary=ContextGroundingSummary(
            present=sum(1 for anchor in anchors if anchor.status == "present"),
            absent=absent,
            contradicted=contradicted,
            loadBearing=sum(1 for anchor in anchors if anchor.loadBearing),
        ),
        notes=["Deterministic context-grounding proxy over supplied context only; not objective truth validation."],
    )
