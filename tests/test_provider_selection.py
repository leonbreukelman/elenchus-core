import pytest

from elenchus_core.providers import resolve_default_provider_config


def test_default_provider_is_deterministic_without_keys():
    assert resolve_default_provider_config({}).provider == "deterministic"


def test_explicit_deterministic_wins_over_keys():
    config = resolve_default_provider_config({"ELENCHUS_LLM_PROVIDER": "deterministic", "GEMINI_API_KEY": "dummy"})
    assert config.provider == "deterministic"
    assert config.model == "heuristic-v0"


def test_preferred_model_requires_matching_provider_family():
    with pytest.raises(ValueError, match="conflicts"):
        resolve_default_provider_config(
            {"ELENCHUS_LLM_PROVIDER": "gemini", "ELENCHUS_PREFERRED_MODEL": "grok-3", "GEMINI_API_KEY": "dummy"}
        )
