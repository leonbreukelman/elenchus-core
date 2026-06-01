from elenchus_core.actions import action_terms, affirmed_term_count, generate_near_neighbor_alternatives
from elenchus_core.lenses import selected_lenses
from elenchus_core.models import EvaluationRequest


def _request(domain: str, action_type: str, hints: list[str] | None = None) -> EvaluationRequest:
    return EvaluationRequest.model_validate(
        {
            "traceId": f"lens-{domain}-{action_type}",
            "domain": domain,
            "domainHints": hints or [],
            "context": "A technical operations context with enough detail for validation.",
            "proposedAction": {"type": action_type, "target": "primary-target", "riskLevel": "medium"},
            "rationale": "The stated rationale has enough detail to validate model construction.",
        }
    )


def test_security_requests_generate_security_cloud_alternatives():
    request = _request("security", "rotate_secret", ["cloud"])

    alternatives = generate_near_neighbor_alternatives(request)
    action_types = {alternative.action.type for alternative in alternatives}

    assert "revoke_token" in action_types
    assert "investigate_more" in action_types
    assert "page_human" in action_types


def test_domain_lens_priority_dedupes_domain_then_hints_then_generic():
    request = _request("cloud", "scale_node_pool", ["security", "cloud", "ai_ml"])

    assert [lens.name for lens in selected_lenses(request)] == ["cloud", "security", "ai_ml", "generic"]


def test_unknown_action_types_get_generic_alternatives_not_crash():
    request = _request("generic", "custom_vendor_action")

    alternatives = generate_near_neighbor_alternatives(request)

    assert alternatives
    assert {alternative.action.type for alternative in alternatives} >= {"investigate_more", "page_human", "no_action"}


def test_sre_action_terms_and_alternative_order_remain_legacy_compatible():
    request = _request("sre", "terminate_idle_sessions")

    assert action_terms("terminate_idle_sessions") == [
        "idle",
        "kill",
        "lock",
        "locks",
        "session",
        "sessions",
        "terminate",
        "terminate idle sessions",
        "vacuum",
    ]
    assert [alternative.action.type for alternative in generate_near_neighbor_alternatives(request)] == [
        "rollback_deployment",
        "increase_iops",
        "restart_service",
        "scale_service",
        "page_human",
    ]


def test_non_sre_lens_composition_does_not_mutate_sre_legacy_outputs():
    baseline = generate_near_neighbor_alternatives(_request("sre", "rollback_deployment"))
    _ = generate_near_neighbor_alternatives(_request("security", "revoke_token", ["cloud", "ai_ml"]))
    after = generate_near_neighbor_alternatives(_request("sre", "rollback_deployment"))

    assert [alternative.action.type for alternative in after] == [alternative.action.type for alternative in baseline]
    assert action_terms("rollback_deployment") == [
        "deploy",
        "deployment",
        "regression",
        "release",
        "roll back",
        "rollback",
        "rollback deployment",
        "version",
    ]


def test_security_lens_terms_extend_action_coupling():
    terms = action_terms("revoke_token", selected_lenses(_request("security", "revoke_token")))

    assert "credential" in terms
    assert "invalidate" in terms
    assert "access" in terms


def test_negated_action_terms_do_not_count_as_affirmed():
    terms = action_terms("rollback_deployment")

    assert affirmed_term_count("Do not rollback the deployment; scale the service instead.", terms) == 0
    assert affirmed_term_count("Scale service rather than rolling back a deployment.", terms) == 0
