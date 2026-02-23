"""Tests for get_llm_config: provider normalization and provider-aware API key env fallback."""
from __future__ import annotations

import os

import pytest

from featureflow.config import DEFAULT_LLM_CONFIG, SUPPORTED_LLM_PROVIDERS, get_llm_config


def test_get_llm_config_provider_normalized_to_lowercase() -> None:
    cfg = get_llm_config({"llm": {"provider": "OPENAI", "enabled": False}})
    assert cfg["provider"] == "openai"

    cfg = get_llm_config({"llm": {"provider": "Anthropic", "enabled": False}})
    assert cfg["provider"] == "anthropic"


def test_get_llm_config_base_url_default_empty() -> None:
    cfg = get_llm_config({})
    assert cfg.get("base_url") == ""


def test_get_llm_config_base_url_from_config() -> None:
    cfg = get_llm_config({"llm": {"base_url": "http://localhost:11434", "enabled": False}})
    assert cfg["base_url"] == "http://localhost:11434"


def test_get_llm_config_openai_api_key_env_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cfg = get_llm_config({"llm": {"provider": "openai", "enabled": False, "api_key": ""}})
    assert cfg["api_key"] == ""

    monkeypatch.setenv("OPENAI_API_KEY", "env-key-openai")
    cfg = get_llm_config({"llm": {"provider": "openai", "enabled": False, "api_key": ""}})
    assert cfg["api_key"] == "env-key-openai"


def test_get_llm_config_anthropic_api_key_env_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    cfg = get_llm_config({"llm": {"provider": "anthropic", "enabled": False, "api_key": ""}})
    assert cfg["api_key"] == ""

    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key-anthropic")
    cfg = get_llm_config({"llm": {"provider": "anthropic", "enabled": False, "api_key": ""}})
    assert cfg["api_key"] == "env-key-anthropic"


def test_get_llm_config_gemini_api_key_env_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    cfg = get_llm_config({"llm": {"provider": "gemini", "enabled": False, "api_key": ""}})
    assert cfg["api_key"] == ""

    monkeypatch.setenv("GOOGLE_API_KEY", "env-key-google")
    cfg = get_llm_config({"llm": {"provider": "gemini", "enabled": False, "api_key": ""}})
    assert cfg["api_key"] == "env-key-google"

    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "env-key-gemini")
    cfg = get_llm_config({"llm": {"provider": "gemini", "enabled": False, "api_key": ""}})
    assert cfg["api_key"] == "env-key-gemini"


def test_get_llm_config_ollama_no_key_required() -> None:
    cfg = get_llm_config({"llm": {"provider": "ollama", "enabled": False, "api_key": ""}})
    assert cfg["api_key"] == ""


def test_get_llm_config_ollama_default_base_url() -> None:
    cfg = get_llm_config({"llm": {"provider": "ollama", "enabled": False, "base_url": ""}})
    assert cfg["base_url"] == "http://localhost:11434"

    cfg = get_llm_config({"llm": {"provider": "ollama", "enabled": False}})
    assert cfg["base_url"] == "http://localhost:11434"


def test_get_llm_config_ollama_base_url_from_config() -> None:
    cfg = get_llm_config({
        "llm": {"provider": "ollama", "enabled": False, "base_url": "http://custom:11434"},
    })
    assert cfg["base_url"] == "http://custom:11434"


def test_get_llm_config_config_api_key_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    cfg = get_llm_config({"llm": {"provider": "openai", "enabled": False, "api_key": "config-key"}})
    assert cfg["api_key"] == "config-key"


def test_supported_providers_include_all_four() -> None:
    assert set(SUPPORTED_LLM_PROVIDERS) == {"openai", "anthropic", "gemini", "ollama"}


def test_default_llm_config_has_base_url() -> None:
    assert "base_url" in DEFAULT_LLM_CONFIG
    assert DEFAULT_LLM_CONFIG["base_url"] == ""
