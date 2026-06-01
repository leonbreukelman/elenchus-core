from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from .hash import sha256_hex
from .models import ContextGroundingAssessment, EvaluationReport, EvaluationRequest, PolicyFinding, SupportAssessment


def safe_audit_trace_id(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip())[:80].strip("-._")
    return cleaned or "trace"


def audit_safe_grounding(grounding: ContextGroundingAssessment) -> dict[str, Any]:
    return {
        "score": grounding.score,
        "summary": grounding.summary.model_dump(mode="json"),
        "anchors": [
            {
                "id": anchor.id,
                "kind": anchor.kind,
                "status": anchor.status,
                "loadBearing": anchor.loadBearing,
                "weight": anchor.weight,
                "textHash": sha256_hex(anchor.text),
            }
            for anchor in grounding.anchors
        ],
    }


def audit_safe_support(support: SupportAssessment) -> dict[str, Any]:
    return {
        "originalSupport": support.originalSupport,
        "strongestAlternativeSupport": support.strongestAlternativeSupport,
        "specificityMargin": support.specificityMargin,
        "strongestAlternativeId": support.strongestAlternativeId,
        "marginReliability": support.marginReliability.model_dump(mode="json") if support.marginReliability else None,
    }


def audit_safe_policy_findings(findings: list[PolicyFinding]) -> list[dict[str, str]]:
    return [{"code": finding.code, "severity": finding.severity} for finding in findings]


def audit_safe_payload(request: EvaluationRequest, report: EvaluationReport) -> dict[str, Any]:
    return {
        "requestDigest": sha256_hex(request.model_dump_json()),
        "requestSummary": {
            "traceId": request.traceId,
            "domain": request.domain,
            "actionType": request.proposedAction.type,
            "actionTargetHash": sha256_hex(request.proposedAction.target) if request.proposedAction.target else None,
            "actionRiskLevel": request.proposedAction.riskLevel,
            "contextHash": sha256_hex(request.context),
            "rationaleHash": sha256_hex(request.rationale),
            "metadataKeys": sorted((request.metadata or {}).keys()),
        },
        "recommendation": report.recommendation,
        "calibration": report.calibration,
        "overallSignal": report.overallSignal,
        "subscores": report.subscores.model_dump(mode="json") if report.subscores else None,
        "support": audit_safe_support(report.support) if report.support else None,
        "grounding": audit_safe_grounding(report.grounding) if report.grounding else None,
        "policyFindings": audit_safe_policy_findings(report.policyFindings),
        "readiness": report.readiness.model_dump(mode="json"),
        "rubric": report.rubric.model_dump(mode="json"),
        "providerMetadata": report.providerMetadata.model_dump(mode="json"),
    }


class FileAuditLogger:
    def __init__(self, directory: str | os.PathLike[str] | None = None) -> None:
        self.directory = Path(directory or os.environ.get("ELENCHUS_AUDIT_DIR", ".elenchus-audit"))

    def write(self, request: EvaluationRequest, report: EvaluationReport) -> str:
        self.directory.mkdir(parents=True, exist_ok=True)
        filename = f"{safe_audit_trace_id(request.traceId)}-{int(time.time() * 1000)}-{uuid4().hex[:8]}.json"
        payload = {
            "traceId": request.traceId,
            "stage": "complete" if report.status == "complete" else report.status,
            "replay": {
                "evaluatorVersion": report.rubric.evaluatorVersion,
                "provider": report.providerMetadata.provider,
                "model": report.providerMetadata.model,
            },
            "payload": audit_safe_payload(request, report),
        }
        (self.directory / filename).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return filename
