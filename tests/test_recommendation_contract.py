from elenchus_core.models import EvaluationRequest, TypedAction
from elenchus_core.report import RECOMMENDATION_CAP_ORDER, _cap_recommendation, build_error_report


def test_recommendation_cap_order_excludes_error_sentinel():
    assert RECOMMENDATION_CAP_ORDER == ("proceed", "proceed_with_caveats", "reconsider", "escalate")
    assert "abort_signal_only" not in RECOMMENDATION_CAP_ORDER


def test_recommendation_cap_uses_single_permissiveness_order():
    assert _cap_recommendation("proceed", "reconsider") == "reconsider"
    assert _cap_recommendation("reconsider", "proceed_with_caveats") == "reconsider"
    assert _cap_recommendation("proceed_with_caveats", "escalate") == "escalate"


def test_error_report_exposes_absent_signal_not_restrictive_cap():
    request = EvaluationRequest(
        traceId="error-contract",
        domain="generic",
        context="A context with enough characters.",
        proposedAction=TypedAction(type="investigate_more"),
        rationale="A rationale with enough characters.",
    )

    report = build_error_report(request, "forced failure")

    assert report.status == "error"
    assert report.recommendation == "abort_signal_only"
    assert report.overallSignal is None
    assert report.confidence is None
    assert report.readiness.advisorySummary == "error_no_numeric_signal"
    assert "incomplete_evaluation" in report.readiness.reviewReasons
