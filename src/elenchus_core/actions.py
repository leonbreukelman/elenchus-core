from __future__ import annotations

import re

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


def normalize_action_type(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    return re.sub(r"_+", "_", cleaned).strip("_")


def action_terms(action_type: str) -> list[str]:
    normalized = normalize_action_type(action_type)
    base = [part for part in normalized.split("_") if part]
    terms = [normalized.replace("_", " "), *base, *ACTION_SYNONYMS.get(normalized, [])]
    return sorted({term for term in terms if term})


def generate_near_neighbor_alternatives(request: EvaluationRequest) -> list[AlternativeAction]:
    original = normalize_action_type(request.proposedAction.type)
    candidates = SRE_ACTION_TYPES if request.domain == "sre" else ["investigate_more", "page_human", "no_action"]
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
