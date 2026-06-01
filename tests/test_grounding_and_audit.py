import json

from elenchus_core.audit import FileAuditLogger
from elenchus_core.evaluator import evaluate_request
from elenchus_core.models import EvaluationRequest, TypedAction


def test_grounding_recognizes_negated_release_as_contradiction():
    request = EvaluationRequest(
        traceId="negated-release",
        domain="sre",
        context="Latency is high, but there was no deployment and no version change today.",
        proposedAction=TypedAction(type="rollback_deployment", target="api", riskLevel="high"),
        rationale="The latest deployment caused a regression, so rollback is the right action.",
    )

    report = evaluate_request(request)

    assert report.grounding is not None
    mechanisms = [anchor for anchor in report.grounding.anchors if anchor.kind == "mechanism"]
    assert any(anchor.status == "contradicted" for anchor in mechanisms)


def test_file_audit_logger_persists_safe_metadata_without_raw_text(tmp_path):
    request = EvaluationRequest(
        traceId="audit-safe-001",
        domain="sre",
        context="CPU saturation is high on checkout-api and p95 latency rose to 1800ms.",
        proposedAction=TypedAction(type="scale_service", target="checkout-api", riskLevel="medium"),
        rationale="Because CPU saturation is high and p95 latency rose to 1800ms, scaling checkout-api adds needed capacity.",
    )
    logger = FileAuditLogger(tmp_path)

    report = evaluate_request(request, audit_logger=logger)

    assert report.auditRef is not None
    payload = json.loads((tmp_path / report.auditRef).read_text())
    serialized = json.dumps(payload)
    assert "CPU saturation is high" not in serialized
    assert "scaling checkout-api" not in serialized
    assert payload["payload"]["requestSummary"]["contextHash"]
    assert payload["payload"]["grounding"]["anchors"]
    assert "textHash" in payload["payload"]["grounding"]["anchors"][0]


def test_file_audit_logger_does_not_persist_raw_structured_evidence_content(tmp_path):
    artifact_content = "ARTIFACT_SENTINEL_DO_NOT_LEAK token [REDACTED_TOKEN] printed in CI build 8127"
    request = EvaluationRequest.model_validate(
        {
            "traceId": "audit-safe-evidence-001",
            "domain": "security",
            "context": "CI build 8127 printed an exposed token and audit marked it urgent.",
            "proposedAction": {"type": "revoke_token", "target": "github-token", "riskLevel": "medium"},
            "rationale": "Because CI build 8127 printed token [REDACTED_TOKEN], revoke the token.",
            "structuredRationale": {
                "claim": "Revoke the exposed token.",
                "grounds": [
                    {"text": "CI build 8127 printed token [REDACTED_TOKEN].", "evidenceRefs": ["ci-log"], "loadBearing": True}
                ],
            },
            "evidenceBundle": [
                {"id": "ci-log", "type": "ci_log", "contentPointer": "ci://8127", "content": artifact_content}
            ],
        }
    )
    logger = FileAuditLogger(tmp_path)

    report = evaluate_request(request, audit_logger=logger)

    assert report.auditRef is not None
    payload = json.loads((tmp_path / report.auditRef).read_text())
    serialized = json.dumps(payload)
    assert "ARTIFACT_SENTINEL_DO_NOT_LEAK" not in serialized
    assert "[REDACTED_TOKEN]" not in serialized
    assert payload["payload"]["requestSummary"]["contextHash"]
