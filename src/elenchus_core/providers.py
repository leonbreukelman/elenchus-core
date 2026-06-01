from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .actions import action_terms, affirmed_term_count
from .models import AlternativeAction, EvaluationRequest, ProviderMetadata, SupportAssessment
from .toulmin import clamp01, score_specificity

DEFAULT_LLM_MODELS = {
    "claude": "claude-sonnet-4-5",
    "grok": "grok-3",
    "gemini": "gemini-3-flash-preview",
    "deterministic": "heuristic-v0",
}


@dataclass(frozen=True)
class ProviderResolutionConfig:
    provider: str
    model: str
    api_key: str | None = None
    key_source: str | None = None


DETERMINISTIC_PROVIDER_METADATA = ProviderMetadata(
    provider="deterministic-local",
    model="heuristic-v0",
    roles={
        "alternativeGenerator": "deterministic_near_neighbor",
        "supportScorer": "deterministic_linguistic_policy_overlay",
    },
    deterministic=True,
)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def normalize_provider_name(value: str | None) -> str | None:
    normalized = _clean(value)
    if normalized is None:
        return None
    normalized = normalized.lower()
    if normalized in {"claude", "anthropic"}:
        return "claude"
    if normalized in {"grok", "xai", "x-ai"}:
        return "grok"
    if normalized in {"gemini", "google"}:
        return "gemini"
    if normalized in {"deterministic", "deterministic-local", "local"}:
        return "deterministic"
    return None


def infer_provider_from_preferred_model(model: str | None) -> str | None:
    value = _clean(model)
    if value is None:
        return None
    lowered = value.lower()
    alias = normalize_provider_name(lowered)
    if alias:
        return alias
    if lowered.startswith("claude"):
        return "claude"
    if lowered.startswith("grok"):
        return "grok"
    if lowered.startswith("gemini"):
        return "gemini"
    return None


def _api_key_for(provider: str, env: Mapping[str, str]) -> tuple[str | None, str]:
    if provider == "claude":
        return _clean(env.get("ANTHROPIC_API_KEY")), "ANTHROPIC_API_KEY"
    if provider == "grok":
        return _clean(env.get("XAI_API_KEY")), "XAI_API_KEY"
    gemini = _clean(env.get("GEMINI_API_KEY"))
    return (gemini, "GEMINI_API_KEY") if gemini else (_clean(env.get("API_KEY")), "API_KEY")


def _model_for(provider: str, env: Mapping[str, str]) -> str:
    preferred = _clean(env.get("ELENCHUS_PREFERRED_MODEL"))
    preferred_provider = infer_provider_from_preferred_model(preferred)
    if preferred and preferred_provider in {None, provider} and normalize_provider_name(preferred) is None:
        return preferred
    if provider == "claude":
        return _clean(env.get("ANTHROPIC_MODEL")) or DEFAULT_LLM_MODELS["claude"]
    if provider == "grok":
        return _clean(env.get("XAI_MODEL")) or DEFAULT_LLM_MODELS["grok"]
    if provider == "gemini":
        return _clean(env.get("GEMINI_MODEL")) or DEFAULT_LLM_MODELS["gemini"]
    return DEFAULT_LLM_MODELS["deterministic"]


def resolve_default_provider_config(env: Mapping[str, str]) -> ProviderResolutionConfig:
    raw_provider = _clean(env.get("ELENCHUS_LLM_PROVIDER"))
    explicit_provider = normalize_provider_name(raw_provider)
    if raw_provider and explicit_provider is None:
        raise ValueError(
            f"Unsupported ELENCHUS_LLM_PROVIDER={raw_provider}; expected claude, grok, gemini, or deterministic"
        )
    preferred = _clean(env.get("ELENCHUS_PREFERRED_MODEL"))
    preferred_provider = infer_provider_from_preferred_model(preferred)
    if preferred and preferred_provider is None and explicit_provider is None:
        raise ValueError(
            "ELENCHUS_PREFERRED_MODEL does not identify a provider family; set ELENCHUS_LLM_PROVIDER explicitly"
        )
    if (
        explicit_provider
        and preferred_provider
        and explicit_provider != preferred_provider
        and preferred_provider != "deterministic"
    ):
        raise ValueError(
            f"ELENCHUS_LLM_PROVIDER={explicit_provider} conflicts with ELENCHUS_PREFERRED_MODEL={preferred}"
        )
    if explicit_provider == "deterministic" or preferred_provider == "deterministic":
        return ProviderResolutionConfig(provider="deterministic", model=DEFAULT_LLM_MODELS["deterministic"])
    provider = explicit_provider or preferred_provider
    if provider:
        key, source = _api_key_for(provider, env)
        if not key:
            raise ValueError(f"ELENCHUS_LLM_PROVIDER={provider} requires {source}")
        return ProviderResolutionConfig(
            provider=provider, model=_model_for(provider, env), api_key=key, key_source=source
        )
    for candidate in ("claude", "grok", "gemini"):
        key, source = _api_key_for(candidate, env)
        if key:
            return ProviderResolutionConfig(
                provider=candidate, model=_model_for(candidate, env), api_key=key, key_source=source
            )
    return ProviderResolutionConfig(provider="deterministic", model=DEFAULT_LLM_MODELS["deterministic"])


def _term_support(text: str, action_type: str) -> float:
    terms = action_terms(action_type)
    if not terms:
        return 0.0
    hits = affirmed_term_count(text, terms)
    return min(1.0, hits / min(len(terms), 6))


def assess_support(request: EvaluationRequest, alternatives: list[AlternativeAction]) -> SupportAssessment:
    specificity = score_specificity(request.rationale, request.proposedAction).value
    original_term_support = _term_support(request.rationale, request.proposedAction.type)
    original = clamp01(0.28 + specificity * 0.42 + original_term_support * 0.3)
    strongest = 0.0
    strongest_id: str | None = None
    combined = f"{request.context}\n{request.rationale}"
    for alternative in alternatives:
        support = clamp01(0.12 + _term_support(combined, alternative.action.type) * 0.45)
        if support > strongest:
            strongest = support
            strongest_id = alternative.id
    return SupportAssessment(
        originalSupport=original,
        strongestAlternativeSupport=strongest,
        specificityMargin=clamp01(original - strongest),
        strongestAlternativeId=strongest_id,
        notes=["Deterministic local support score; no provider calibration claim."],
    )
