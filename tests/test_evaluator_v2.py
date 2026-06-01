from elenchus_core import evaluate_request
from elenchus_core.hash import sha256_hex
from elenchus_core.models import EvaluationRequest, TypedAction


def _structured_request(*, content: str, sha256: str | None = None, refs: list[str] | None = None) -> EvaluationRequest:
    artifact = {
        "id": "ci-log-8127",
        "type": "ci_log",
        "contentPointer": "ci://builds/8127/log#L42",
        "content": content,
    }
    if sha256 is not None:
        artifact["sha256"] = sha256
    return EvaluationRequest.model_validate(
        {
            "traceId": "security-evaluator-v2",
            "domain": "security",
            "context": "CI build 8127 printed GitHub token [REDACTED_TOKEN] in logs and audit marked it exposed.",
            "proposedAction": {"type": "revoke_token", "target": "github-token", "riskLevel": "medium"},
            "rationale": "Because CI build 8127 printed GitHub token [REDACTED_TOKEN] in logs, revoking the token removes immediate access risk.",
            "structuredRationale": {
                "claim": "Revoke the exposed GitHub token.",
                "grounds": [
                    {
                        "text": "CI build 8127 printed GitHub token [REDACTED_TOKEN] in logs.",
                        "evidenceRefs": refs if refs is not None else ["ci-log-8127"],
                        "loadBearing": True,
                    }
                ],
                "warrants": ["Exposed valid credentials can be abused."],
                "rejectedAlternatives": [
                    {"actionId": "rotate_secret", "reason": "Rotation is useful after immediate revocation."}
                ],
                "uncertainty": ["The exposure window is unknown."],
                "wouldChangeIf": ["If the token was already revoked, do not revoke it again."],
            },
            "evidenceBundle": [artifact],
        }
    )


def test_resolved_structured_rationale_scores_above_eloquent_unresolved_rationale():
    content = "CI build 8127 printed GitHub token [REDACTED_TOKEN] in logs and audit marked it exposed."
    resolved = evaluate_request(_structured_request(content=content, sha256=sha256_hex(content)))
    unresolved_request = _structured_request(content=content, sha256=sha256_hex(content), refs=[])
    unresolved = evaluate_request(unresolved_request)

    assert resolved.status == "complete"
    assert unresolved.status == "complete"
    assert resolved.evidenceResolution is not None
    assert unresolved.evidenceResolution is not None
    assert resolved.subscores is not None
    assert unresolved.subscores is not None
    assert resolved.evidenceResolution.score > unresolved.evidenceResolution.score
    assert resolved.subscores.contextGrounding > unresolved.subscores.contextGrounding


def test_mechanical_hash_mismatch_caps_recommendation_and_adds_review_reason():
    request = _structured_request(content="CI log says token [REDACTED_TOKEN] was exposed.", sha256="f" * 64)

    report = evaluate_request(request)

    assert report.status == "complete"
    assert report.evidenceResolution is not None
    assert report.evidenceResolution.summary.hashMismatch == 1
    assert report.recommendation in {"reconsider", "escalate"}
    assert "evidence_hash_mismatch" in report.readiness.reviewReasons
    assert any("hash" in weakness.lower() for weakness in report.topWeaknesses)


def test_method_trust_marks_counterfactual_probe_not_run():
    content = "CI build 8127 printed GitHub token [REDACTED_TOKEN] in logs and audit marked it exposed."

    report = evaluate_request(_structured_request(content=content, sha256=sha256_hex(content)))

    assert report.methodTrust.structural == "deterministic"
    assert report.methodTrust.evidenceResolution == "self_consistent_artifact_hash"
    assert report.methodTrust.counterfactualProbe == "not_run"
    assert any("Counterfactual probing was not run" in note for note in report.methodTrust.notes)


def test_product_semantics_uses_evidence_auditor_language_without_action_correctness_claims():
    content = "CI build 8127 printed GitHub token [REDACTED_TOKEN] in logs and audit marked it exposed."

    report = evaluate_request(_structured_request(content=content, sha256=sha256_hex(content)))

    assert "task-local evidence-resolving explanation-quality auditor" in report.productSemantics
    assert "public structured rationale" in report.productSemantics
    assert "advisory signal only" in report.productSemantics
    assert "does not judge action correctness" in report.productSemantics
    assert "objective truth" in report.productSemantics
    assert "hidden CoT" in report.productSemantics


def test_error_report_includes_method_trust_and_no_fake_evidence_signal():
    request = EvaluationRequest(
        traceId="bad-provider-v2",
        domain="security",
        context="A context with enough security detail.",
        proposedAction=TypedAction(type="revoke_token", target="github-token"),
        rationale="A rationale with enough security detail.",
    )

    report = evaluate_request(request, provider="broken")

    assert report.status == "error"
    assert report.evidenceResolution is None
    assert report.methodTrust.counterfactualProbe == "not_run"
    assert report.methodTrust.evidenceResolution == "not_available"
    assert report.overallSignal is None
    assert report.subscores is None


def test_partial_structured_request_without_evidence_bundle_degrades_safely():
    request = EvaluationRequest.model_validate(
        {
            "traceId": "partial-structured-v2",
            "domain": "security",
            "context": "A token was discussed in incident notes, but no evidence bundle was supplied.",
            "proposedAction": {"type": "revoke_token", "target": "github-token"},
            "rationale": "Because the token appears exposed, revoke it pending operator review.",
            "structuredRationale": {
                "claim": "Revoke the token.",
                "grounds": [{"text": "The token appears exposed.", "evidenceRefs": ["missing-artifact"]}],
            },
        }
    )

    report = evaluate_request(request)

    assert report.status == "complete"
    assert report.evidenceResolution is not None
    assert report.evidenceResolution.summary.missingRef == 1
    assert report.methodTrust.evidenceResolution == "missing_or_unresolved_refs"
    assert report.recommendation in {"proceed_with_caveats", "reconsider", "escalate"}


def test_advisory_support_score_does_not_change_overall_signal_or_recommendation():
    supported_content = "CI build 8127 printed GitHub token [REDACTED_TOKEN] in logs; revoke token github-token."
    unsupported_content = "CI build 8127 unrelated timing note; revoke token github-token."

    supported = evaluate_request(_structured_request(content=supported_content, sha256=sha256_hex(supported_content)))
    unsupported = evaluate_request(_structured_request(content=unsupported_content, sha256=sha256_hex(unsupported_content)))

    assert supported.evidenceResolution is not None
    assert unsupported.evidenceResolution is not None
    assert supported.evidenceResolution.mechanicalScore == unsupported.evidenceResolution.mechanicalScore
    assert supported.evidenceResolution.supportScore > unsupported.evidenceResolution.supportScore
    assert supported.subscores is not None
    assert unsupported.subscores is not None
    assert supported.subscores.contextGrounding == unsupported.subscores.contextGrounding
    assert supported.overallSignal == unsupported.overallSignal
    assert supported.recommendation == unsupported.recommendation


def test_unverifiable_hash_has_distinct_review_reason_from_hash_mismatch():
    request = _structured_request(content="CI log says token [REDACTED_TOKEN] was exposed.")
    assert request.evidenceBundle is not None
    request.evidenceBundle[0].content = None
    request.evidenceBundle[0].sha256 = "a" * 64

    report = evaluate_request(request)

    assert report.evidenceResolution is not None
    assert report.evidenceResolution.summary.hashUnverifiable == 1
    assert "evidence_hash_unverifiable" in report.readiness.reviewReasons
    assert "evidence_hash_mismatch" not in report.readiness.reviewReasons
