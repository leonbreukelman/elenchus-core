from elenchus_core.evidence import assess_evidence_resolution
from elenchus_core.hash import sha256_hex
from elenchus_core.models import EvaluationRequest


def _request_with_ground(
    *,
    ground_text: str,
    refs: list[str],
    artifacts: list[dict],
    action_type: str = "revoke_token",
    action_target: str = "github-token",
) -> EvaluationRequest:
    return EvaluationRequest.model_validate(
        {
            "traceId": "evidence-resolution-001",
            "domain": "security",
            "context": "Security audit context with enough characters.",
            "proposedAction": {"type": action_type, "target": action_target, "riskLevel": "medium"},
            "rationale": ground_text if len(ground_text) >= 10 else f"{ground_text} because evidence exists",
            "structuredRationale": {
                "claim": f"Perform {action_type} on {action_target}.",
                "grounds": [{"text": ground_text, "evidenceRefs": refs, "loadBearing": True}],
            },
            "evidenceBundle": artifacts,
        }
    )


def test_matching_hash_pointer_and_content_scores_high_and_supported():
    content = "CI build 8127 log: GitHub token [REDACTED_TOKEN] was printed in CI logs and remains valid."
    request = _request_with_ground(
        ground_text="CI build 8127 shows GitHub token [REDACTED_TOKEN] printed in CI logs.",
        refs=["ci-log-8127"],
        artifacts=[
            {
                "id": "ci-log-8127",
                "type": "ci_log",
                "contentPointer": "ci://builds/8127/log#L42",
                "content": content,
                "sha256": sha256_hex(content),
            }
        ],
    )

    assessment = assess_evidence_resolution(request)

    assert assessment is not None
    assert assessment.mechanicalScore >= 0.95
    assert assessment.summary.resolved == 1
    assert assessment.summary.hashVerified == 1
    assert assessment.summary.supported == 1
    assert assessment.grounds[0].supportStatus == "supported"


def test_missing_ref_records_mechanical_failure_and_low_score():
    request = _request_with_ground(
        ground_text="CI logs show GitHub token [REDACTED_TOKEN] printed in build 8127.",
        refs=["missing-log"],
        artifacts=[],
    )

    assessment = assess_evidence_resolution(request)

    assert assessment is not None
    assert assessment.summary.missingRef == 1
    assert assessment.mechanicalScore < 0.5
    assert "missing_ref" in assessment.grounds[0].mechanicalStatuses


def test_hash_mismatch_records_failure_and_does_not_verify_hash():
    content = "CI log says token [REDACTED_TOKEN] was exposed."
    request = _request_with_ground(
        ground_text="CI log says token [REDACTED_TOKEN] was exposed.",
        refs=["ci-log"],
        artifacts=[
            {
                "id": "ci-log",
                "type": "ci_log",
                "contentPointer": "ci://builds/1/log#L1",
                "content": content,
                "sha256": "f" * 64,
            }
        ],
    )

    assessment = assess_evidence_resolution(request)

    assert assessment is not None
    assert assessment.summary.hashMismatch == 1
    assert assessment.summary.hashVerified == 0
    assert "hash_mismatch" in assessment.grounds[0].mechanicalStatuses
    assert assessment.mechanicalScore < 0.8


def test_polished_load_bearing_ground_with_no_refs_is_unresolved():
    request = _request_with_ground(
        ground_text="The incident narrative is specific and confident, so revoking the token is clearly the right move.",
        refs=[],
        artifacts=[],
    )

    assessment = assess_evidence_resolution(request)

    assert assessment is not None
    assert assessment.summary.unreferencedLoadBearing == 1
    assert assessment.summary.unresolved == 1
    assert assessment.score < 0.5


def test_keyword_stuffed_ground_without_action_evidence_is_not_supported():
    content = "checkout-api p95 latency 1800ms cpu saturation 96% replicas 2 disk queue 40"
    request = _request_with_ground(
        ground_text="checkout-api p95 latency 1800ms cpu saturation 96% replicas 2 disk queue 40 means the GitHub token must be revoked.",
        refs=["metrics"],
        artifacts=[
            {
                "id": "metrics",
                "type": "metric_snapshot",
                "contentPointer": "metrics://checkout-api/now",
                "content": content,
                "sha256": sha256_hex(content),
            }
        ],
    )

    assessment = assess_evidence_resolution(request)

    assert assessment is not None
    assert assessment.summary.resolved == 1
    assert assessment.grounds[0].supportStatus == "unresolved"
    assert assessment.summary.supported == 0


def test_consistent_negated_fact_is_not_advisory_contradiction():
    content = "error budget remaining: no error budget remaining for checkout-api in this window"
    request = _request_with_ground(
        ground_text="There is no error budget remaining for checkout-api.",
        refs=["slo"],
        artifacts=[
            {
                "id": "slo",
                "type": "slo_report",
                "contentPointer": "slo://checkout-api/current",
                "content": content,
                "sha256": sha256_hex(content),
            }
        ],
        action_type="page_human",
        action_target="checkout-api",
    )

    assessment = assess_evidence_resolution(request)

    assert assessment is not None
    assert assessment.summary.advisoryContradiction == 0
    assert assessment.grounds[0].supportStatus != "advisory_contradiction"


def test_sha256_with_no_content_is_unverifiable_pointer_unresolved():
    request = _request_with_ground(
        ground_text="CI log says token [REDACTED_TOKEN] was exposed.",
        refs=["ci-log"],
        artifacts=[
            {
                "id": "ci-log",
                "type": "ci_log",
                "contentPointer": "ci://builds/1/log#L1",
                "sha256": "a" * 64,
            }
        ],
    )

    assessment = assess_evidence_resolution(request)

    assert assessment is not None
    assert assessment.summary.pointerUnresolved == 1
    assert assessment.summary.hashUnverifiable == 1
    assert assessment.summary.hashVerified == 0
    assert "pointer_unresolved" in assessment.grounds[0].mechanicalStatuses


def test_duplicate_artifact_ids_are_flagged_and_unresolved():
    request = _request_with_ground(
        ground_text="CI log says token [REDACTED_TOKEN] was exposed.",
        refs=["ci-log"],
        artifacts=[
            {"id": "ci-log", "type": "ci_log", "contentPointer": "ci://1", "content": "first token [REDACTED_TOKEN]"},
            {"id": "ci-log", "type": "ci_log", "contentPointer": "ci://2", "content": "second token [REDACTED_TOKEN]"},
        ],
    )

    assessment = assess_evidence_resolution(request)

    assert assessment is not None
    assert assessment.summary.duplicateArtifactId >= 1
    assert assessment.summary.resolved == 0
    assert "duplicate_artifact_id" in assessment.grounds[0].mechanicalStatuses


def test_mixed_valid_and_missing_refs_cannot_get_perfect_mechanical_score():
    content = "CI log says token [REDACTED_TOKEN] was exposed in build 8127."
    request = _request_with_ground(
        ground_text="CI log says token [REDACTED_TOKEN] was exposed in build 8127.",
        refs=["ci-log", "missing-log"],
        artifacts=[
            {
                "id": "ci-log",
                "type": "ci_log",
                "contentPointer": "ci://builds/8127/log#L1",
                "content": content,
                "sha256": sha256_hex(content),
            }
        ],
    )

    assessment = assess_evidence_resolution(request)

    assert assessment is not None
    assert assessment.summary.resolved == 1
    assert assessment.summary.missingRef == 1
    assert assessment.mechanicalScore < 1.0


def test_opposite_polarity_is_advisory_contradiction_not_mechanical_failure():
    content = "error budget remaining for checkout-api in this window, checkout-api owner should review"
    request = _request_with_ground(
        ground_text="There is no error budget remaining for checkout-api.",
        refs=["slo"],
        artifacts=[
            {
                "id": "slo",
                "type": "slo_report",
                "contentPointer": "slo://checkout-api/current",
                "content": content,
                "sha256": sha256_hex(content),
            }
        ],
        action_type="page_human",
        action_target="checkout-api",
    )

    assessment = assess_evidence_resolution(request)

    assert assessment is not None
    assert assessment.summary.advisoryContradiction == 1
    assert assessment.summary.resolved == 1
    assert assessment.summary.hashVerified == 1
    assert assessment.summary.hashMismatch == 0
    assert assessment.grounds[0].supportStatus == "advisory_contradiction"
