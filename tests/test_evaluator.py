from elenchus_core import evaluate_request
from elenchus_core.models import EvaluationRequest, TypedAction


def test_strong_sre_rationale_produces_complete_internal_alpha_report():
    request = EvaluationRequest(
        traceId="sre-monitor-001",
        domain="sre",
        context=(
            "Postgres primary shows 95% I/O wait. pg_stat_activity reports 12 idle in transaction "
            "sessions older than 30 minutes holding locks on audit_logs. VACUUM is blocked."
        ),
        proposedAction=TypedAction(
            type="terminate_idle_sessions",
            target="postgres-primary",
            parameters={"maxIdleAgeMinutes": 30, "relation": "audit_logs"},
            riskLevel="medium",
        ),
        rationale=(
            "Because 12 idle in transaction sessions older than 30 minutes are holding locks on audit_logs "
            "and blocking VACUUM, terminating sessions older than 30 minutes releases the locks and addresses "
            "the specific cause rather than only adding capacity."
        ),
    )

    report = evaluate_request(request)

    assert report.status == "complete"
    assert report.calibration == "uncalibrated_internal_alpha"
    assert report.overallSignal is not None and report.overallSignal >= 0.6
    assert report.subscores is not None
    assert report.subscores.contextGrounding >= 0.6
    assert report.grounding is not None
    assert report.grounding.summary.present >= 2
    assert report.readiness.operatorReviewRequired is True
    assert "production_allow_deny" in report.readiness.blockedUses
    assert report.support is not None
    assert report.support.marginReliability is not None


def test_unsupported_specific_rationale_is_capped_by_grounding():
    request = EvaluationRequest(
        traceId="sre-monitor-unsupported",
        domain="sre",
        context="Checkout API latency is high. Error rate is normal. No deployment or version change happened today. CPU is normal.",
        proposedAction=TypedAction(type="rollback_deployment", target="checkout-api", riskLevel="high"),
        rationale="The latest deployment caused a regression, so rolling back the deployment will remove the bad version and restore latency.",
    )

    report = evaluate_request(request)

    assert report.status == "complete"
    assert report.recommendation in {"reconsider", "escalate"}
    assert report.grounding is not None
    assert report.grounding.summary.contradicted >= 1
    assert "contradicted_grounding" in report.readiness.reviewReasons
    assert report.readiness.reviewNeeded is True


def test_error_report_has_no_fake_numeric_signal():
    request = EvaluationRequest(
        traceId="bad-provider",
        domain="generic",
        context="A context with enough characters.",
        proposedAction=TypedAction(type="do_thing"),
        rationale="A rationale with enough characters.",
    )

    report = evaluate_request(request, provider="broken")

    assert report.status == "error"
    assert report.overallSignal is None
    assert report.subscores is None
    assert report.support is None
    assert report.grounding is None
    assert report.confidence is None
    assert report.recommendation == "abort_signal_only"
