from __future__ import annotations

import re

from .actions import action_terms
from .models import LinguisticSpecificityScore, SpecificityFeatures, ToulminArgument, TypedAction

NUMERIC_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:%|ms|s|sec|secs|seconds?|m|min|mins|minutes?|h|hr|hrs|hours?|days?|x|mb|gb|iops)?\b", re.I
)
CAUSAL_RE = re.compile(
    r"\b(because|therefore|so|caused?|drives?|due to|rather than|addresses|releases|blocks?|prevents?)\b", re.I
)
EVIDENCE_RE = re.compile(
    r"\b(shows?|reports?|observed|measured|metric|trace|log|pg_stat_activity|evidence|p\d+)\b", re.I
)
HEDGE_RE = re.compile(r"\b(maybe|probably|possibly|might|could|seems|appears|guess|likely)\b", re.I)
DOMAIN_RE = re.compile(
    r"\b(latency|error|cpu|memory|i/o|io wait|iowait|iops|locks?|vacuum|deployment|release|queue|backlog|sessions?|postgres|service|pod)\b",
    re.I,
)


def _clauses(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"[.;]\s+|\n+", text) if part.strip()]


def clamp01(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)


def score_specificity(rationale: str, action: TypedAction) -> LinguisticSpecificityScore:
    terms = action_terms(action.type)
    lowered = rationale.lower()
    action_hits = sum(1 for term in terms if term in lowered)
    features = SpecificityFeatures(
        numericThresholds=len(NUMERIC_RE.findall(rationale)),
        causalConnectors=len(CAUSAL_RE.findall(rationale)),
        domainTerms=len(DOMAIN_RE.findall(rationale)),
        actionTerms=action_hits,
        evidenceMarkers=len(EVIDENCE_RE.findall(rationale)),
        hedgeTerms=len(HEDGE_RE.findall(rationale)),
    )
    value = clamp01(
        0.24
        + min(features.numericThresholds, 4) * 0.08
        + min(features.causalConnectors, 4) * 0.08
        + min(features.domainTerms, 6) * 0.045
        + min(features.actionTerms, 5) * 0.055
        + min(features.evidenceMarkers, 3) * 0.06
        - min(features.hedgeTerms, 4) * 0.05
    )
    notes = ["Deterministic linguistic specificity proxy; not a truth score."]
    if features.numericThresholds == 0:
        notes.append("No explicit numeric threshold detected.")
    if features.causalConnectors == 0:
        notes.append("No explicit causal connector detected.")
    return LinguisticSpecificityScore(value=value, features=features, notes=notes)


def extract_toulmin_argument(rationale: str, action: TypedAction) -> ToulminArgument:
    clauses = _clauses(rationale)
    claim = clauses[0] if clauses else rationale.strip()
    grounds = [clause for clause in clauses if EVIDENCE_RE.search(clause) or NUMERIC_RE.search(clause)]
    warrants = [clause for clause in clauses if CAUSAL_RE.search(clause)]
    qualifiers = [match.group(0) for match in HEDGE_RE.finditer(rationale)]
    rebuttals = [clause for clause in clauses if re.search(r"\b(rather than|instead of|but|however)\b", clause, re.I)]
    return ToulminArgument(
        claim=claim,
        grounds=grounds,
        warrants=warrants,
        backing=[],
        qualifiers=qualifiers,
        rebuttals=rebuttals,
        specificity=score_specificity(rationale, action),
    )
