import pytest
from pydantic import ValidationError

from elenchus_core.models import EvaluationRequest, TypedAction


def _evidence_request_payload() -> dict:
    return {
        "traceId": "security-evidence-001",
        "domain": "security",
        "domainHints": ["cloud"],
        "context": "A token audit found an exposed GitHub token in CI logs for build 8127.",
        "availableActions": [
            {"type": "revoke_token", "target": "github-token"},
            {"type": "rotate_secret", "target": "github-token"},
            {"type": "investigate_more", "target": "ci-logs"},
        ],
        "proposedAction": {"type": "revoke_token", "target": "github-token", "riskLevel": "medium"},
        "rationale": "Because CI logs show token [REDACTED_TOKEN] in build 8127, revoking the token removes immediate access risk.",
        "structuredRationale": {
            "claim": "Revoke the exposed GitHub token.",
            "grounds": [
                {
                    "text": "CI logs show token [REDACTED_TOKEN] in build 8127.",
                    "evidenceRefs": ["log-ci-8127"],
                    "loadBearing": True,
                }
            ],
            "warrants": ["Exposed credentials can be abused while valid."],
            "assumptions": ["The token is still valid."],
            "rejectedAlternatives": [
                {"actionId": "rotate_secret", "reason": "Rotation is follow-up after immediate revocation."}
            ],
            "uncertainty": ["Exact exposure window is unknown."],
            "wouldChangeIf": ["If the token was already revoked, do not revoke it again."],
        },
        "evidenceBundle": [
            {
                "id": "log-ci-8127",
                "type": "ci_log",
                "contentPointer": "ci://builds/8127/log#L42",
                "content": "build 8127 log line 42: token [REDACTED_TOKEN] was printed in CI logs",
                "sha256": "placeholder-filled-by-test",
            }
        ],
    }


def test_structured_rationale_evidence_bundle_and_domain_hints_are_accepted():
    payload = _evidence_request_payload()
    payload["evidenceBundle"][0]["sha256"] = "0" * 64

    request = EvaluationRequest.model_validate(payload)

    assert request.domain == "security"
    assert request.domainHints == ["cloud"]
    assert request.structuredRationale is not None
    assert request.structuredRationale.grounds[0].evidenceRefs == ["log-ci-8127"]
    assert request.evidenceBundle is not None
    assert request.evidenceBundle[0].contentPointer == "ci://builds/8127/log#L42"
    assert request.availableActions is not None
    assert request.availableActions[0].type == "revoke_token"


def test_legacy_free_text_request_shape_still_validates():
    request = EvaluationRequest(
        traceId="legacy-valid-001",
        domain="sre",
        context="Postgres has 95% I/O wait and idle sessions holding locks.",
        proposedAction=TypedAction(type="terminate_idle_sessions", target="postgres"),
        rationale="Because idle sessions hold locks, terminate idle sessions to unblock work.",
    )

    assert request.structuredRationale is None
    assert request.evidenceBundle is None
    assert request.domainHints == []


def test_evidence_bundle_artifact_count_is_bounded():
    payload = _evidence_request_payload()
    payload["evidenceBundle"] = [
        {"id": f"artifact-{idx}", "type": "log", "content": "small content", "contentPointer": f"log://{idx}"}
        for idx in range(51)
    ]

    with pytest.raises(ValidationError):
        EvaluationRequest.model_validate(payload)


def test_evidence_artifact_content_length_is_bounded():
    payload = _evidence_request_payload()
    payload["evidenceBundle"][0]["content"] = "x" * 20_001

    with pytest.raises(ValidationError):
        EvaluationRequest.model_validate(payload)


def test_total_evidence_bundle_content_is_bounded():
    payload = _evidence_request_payload()
    payload["evidenceBundle"] = [
        {"id": f"artifact-{idx}", "type": "log", "content": "x" * 4_001, "contentPointer": f"log://{idx}"}
        for idx in range(50)
    ]

    with pytest.raises(ValidationError):
        EvaluationRequest.model_validate(payload)
