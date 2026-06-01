from __future__ import annotations

import re

from .lenses import DomainLens, selected_lenses
from .models import AlternativeAction, EvaluationRequest, TypedAction

SRE_ACTION_TYPES = [
    "terminate_idle_sessions",
    "rollback_deployment",
    "increase_iops",
    "restart_service",
    "scale_service",
    "page_human",
    "investigate_more",
    "no_action",
]

ACTION_SYNONYMS: dict[str, list[str]] = {
    "terminate_idle_sessions": ["terminate", "kill", "idle", "session", "sessions", "lock", "locks", "vacuum"],
    "rollback_deployment": ["rollback", "roll back", "deployment", "deploy", "release", "version", "regression"],
    "increase_iops": ["iops", "disk", "storage", "capacity", "throughput", "io", "i/o"],
    "restart_service": ["restart", "reboot", "service", "pod", "worker"],
    "scale_service": ["scale", "capacity", "replica", "cpu", "memory", "service"],
    "page_human": ["page", "human", "on-call", "owner", "operator", "escalate"],
    "investigate_more": ["investigate", "inspect", "gather", "logs", "metrics"],
    "no_action": ["no action", "wait", "monitor", "observe"],
}
NEGATING_TERM_PREFIXES = (
    "instead of",
    "rather than",
    "not",
    "no",
    "without",
    "avoid",
    "avoiding",
    "do not",
    "don't",
)


def normalize_action_type(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    return re.sub(r"_+", "_", cleaned).strip("_")


def action_terms(action_type: str, lenses: list[DomainLens] | None = None) -> list[str]:
    normalized = normalize_action_type(action_type)
    base = [part for part in normalized.split("_") if part]
    synonyms = list(ACTION_SYNONYMS.get(normalized, []))
    if lenses is not None:
        for lens in lenses:
            synonyms.extend(lens.action_synonyms.get(normalized, ()))
    terms = [normalized.replace("_", " "), *base, *synonyms]
    return sorted({term for term in terms if term})


def affirmed_term_count(text: str, terms: list[str]) -> int:
    lowered = text.lower()
    hits = 0
    for term in terms:
        pattern = re.compile(rf"(?<![a-z0-9]){re.escape(term.lower())}(?![a-z0-9])")
        for match in pattern.finditer(lowered):
            prefix_window = lowered[max(0, match.start() - 80) : match.start()]
            if any(
                re.search(rf"\b{re.escape(prefix)}\b[^.?!;:,]*$", prefix_window) for prefix in NEGATING_TERM_PREFIXES
            ):
                continue
            hits += 1
            break
    return hits


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _candidate_action_types(request: EvaluationRequest) -> list[str]:
    if request.domain == "sre" and not request.domainHints and request.availableActions is None:
        return list(SRE_ACTION_TYPES)
    candidates: list[str] = []
    if request.availableActions is not None:
        for action in request.availableActions:
            _append_unique(candidates, normalize_action_type(action.type))
    for lens in selected_lenses(request):
        for action_type in lens.action_types:
            _append_unique(candidates, normalize_action_type(action_type))
    if not candidates:
        candidates = ["investigate_more", "page_human", "no_action"]
    return candidates


def generate_near_neighbor_alternatives(request: EvaluationRequest) -> list[AlternativeAction]:
    original = normalize_action_type(request.proposedAction.type)
    candidates = _candidate_action_types(request)
    alternatives: list[AlternativeAction] = []
    for index, candidate in enumerate([item for item in candidates if item != original], start=1):
        alternatives.append(
            AlternativeAction(
                id=f"alt-{index}-{candidate}",
                action=TypedAction(
                    type=candidate, target=request.proposedAction.target, riskLevel=request.proposedAction.riskLevel
                ),
                rationale=f"A near-neighbor alternative would {candidate.replace('_', ' ')} instead of {original.replace('_', ' ')}.",
                contrastWithOriginal=f"Tests whether the same rationale also supports {candidate.replace('_', ' ')}.",
            )
        )
    return alternatives[:5]
