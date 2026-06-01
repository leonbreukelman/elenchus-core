from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import EvaluationRequest


@dataclass(frozen=True)
class DomainLens:
    name: str
    version: str
    action_types: tuple[str, ...]
    action_synonyms: dict[str, tuple[str, ...]] = field(default_factory=dict)
    artifact_types: tuple[str, ...] = ()
    risk_predicates: tuple[str, ...] = ()
    evidence_markers: tuple[str, ...] = ()
    perturbation_templates: tuple[str, ...] = ()


LENSES: dict[str, DomainLens] = {
    "sre": DomainLens(
        name="sre",
        version="2026-06-01.1",
        action_types=(
            "terminate_idle_sessions",
            "rollback_deployment",
            "increase_iops",
            "restart_service",
            "scale_service",
            "page_human",
            "investigate_more",
            "no_action",
        ),
        artifact_types=("log", "metric_snapshot", "trace", "runbook", "incident_ticket"),
        risk_predicates=("latency", "saturation", "error_rate", "lock_contention", "regression"),
        evidence_markers=("metric", "log", "trace", "dashboard", "ticket"),
    ),
    "security": DomainLens(
        name="security",
        version="2026-06-01.1",
        action_types=(
            "revoke_token",
            "rotate_secret",
            "disable_account",
            "quarantine_host",
            "investigate_more",
            "page_human",
            "no_action",
        ),
        action_synonyms={
            "revoke_token": ("revoke", "token", "credential", "invalidate", "access"),
            "rotate_secret": ("rotate", "secret", "key", "credential", "token"),
            "disable_account": ("disable", "account", "user", "identity"),
            "quarantine_host": ("quarantine", "isolate", "host", "endpoint"),
        },
        artifact_types=("ci_log", "audit_log", "iam_policy", "secret_scan", "edr_alert"),
        risk_predicates=("credential_exposure", "privilege", "lateral_movement", "exfiltration"),
        evidence_markers=("audit", "scan", "alert", "hash", "principal", "token"),
    ),
    "cloud": DomainLens(
        name="cloud",
        version="2026-06-01.1",
        action_types=(
            "scale_node_pool",
            "rollback_deployment",
            "restart_service",
            "rotate_secret",
            "increase_iops",
            "investigate_more",
            "page_human",
            "no_action",
        ),
        action_synonyms={
            "scale_node_pool": ("scale", "node", "nodepool", "cluster", "capacity"),
            "increase_iops": ("iops", "disk", "volume", "throughput", "storage"),
        },
        artifact_types=("cloud_metric", "terraform_plan", "kubernetes_event", "billing_event"),
        risk_predicates=("quota", "capacity", "region", "availability", "iam"),
        evidence_markers=("cloudwatch", "stackdriver", "kubectl", "terraform", "audit"),
    ),
    "software": DomainLens(
        name="software",
        version="2026-06-01.1",
        action_types=(
            "rollback_deployment",
            "revert_commit",
            "disable_feature_flag",
            "add_regression_test",
            "investigate_more",
            "page_human",
            "no_action",
        ),
        action_synonyms={
            "revert_commit": ("revert", "commit", "change", "patch"),
            "disable_feature_flag": ("feature", "flag", "disable", "toggle"),
            "add_regression_test": ("test", "regression", "coverage", "fixture"),
        },
        artifact_types=("diff", "test_log", "issue", "pull_request", "stack_trace"),
        risk_predicates=("regression", "compatibility", "coverage", "data_loss"),
        evidence_markers=("test", "diff", "trace", "issue", "pr"),
    ),
    "ai_ml": DomainLens(
        name="ai_ml",
        version="2026-06-01.1",
        action_types=(
            "rollback_model",
            "disable_model_route",
            "increase_eval_coverage",
            "quarantine_dataset",
            "investigate_more",
            "page_human",
            "no_action",
        ),
        action_synonyms={
            "rollback_model": ("rollback", "model", "checkpoint", "version"),
            "disable_model_route": ("disable", "route", "model", "traffic"),
            "quarantine_dataset": ("quarantine", "dataset", "data", "contamination"),
        },
        artifact_types=("eval_report", "model_card", "dataset_manifest", "inference_log"),
        risk_predicates=("drift", "regression", "toxicity", "hallucination", "contamination"),
        evidence_markers=("eval", "benchmark", "dataset", "trace", "sample"),
    ),
    "tech": DomainLens(
        name="tech",
        version="2026-06-01.1",
        action_types=("investigate_more", "page_human", "no_action"),
        artifact_types=("log", "metric", "ticket", "diff"),
        risk_predicates=("reliability", "security", "cost", "quality"),
        evidence_markers=("log", "metric", "artifact", "ticket"),
    ),
    "generic": DomainLens(
        name="generic",
        version="2026-06-01.1",
        action_types=("investigate_more", "page_human", "no_action"),
        action_synonyms={
            "investigate_more": ("investigate", "inspect", "gather", "logs", "evidence"),
            "page_human": ("page", "human", "operator", "owner", "review"),
            "no_action": ("no action", "wait", "monitor", "observe"),
        },
        artifact_types=("artifact", "log", "note"),
        risk_predicates=("unknown", "uncertain"),
        evidence_markers=("evidence", "artifact", "record"),
    ),
}


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def selected_lenses(request: EvaluationRequest) -> list[DomainLens]:
    names: list[str] = []
    if request.domain != "generic":
        _append_unique(names, request.domain)
    for hint in request.domainHints:
        if hint != "generic":
            _append_unique(names, hint)
    _append_unique(names, "generic")
    return [LENSES[name] for name in names if name in LENSES]
