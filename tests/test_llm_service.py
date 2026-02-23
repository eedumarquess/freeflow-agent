from __future__ import annotations

import json

import pytest

import featureflow.llm.service as llm_service


def _cfg(
    enabled: bool = True,
    provider: str = "openai",
    api_key: str = "test-key",
    base_url: str = "",
    **overrides: object,
) -> dict:
    cfg = {
        "llm": {
            "enabled": enabled,
            "provider": provider,
            "model": "gpt-4.1-mini",
            "api_key": api_key,
            "base_url": base_url,
            "timeout_seconds": 30,
            "temperature": 0,
            "max_repo_tree_entries": 10,
            "max_diff_chars": 50,
            "max_key_file_chars": 20,
        }
    }
    if overrides:
        cfg["llm"].update(overrides)
    return cfg


def _mock_invoker_returning(raw_json: str):
    def _invoker(_prompt: str, _payload: dict, _cfg: dict) -> str:
        return raw_json
    return _invoker


def test_generate_plan_returns_validated_output(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "change_request_md": "# Change Request\n\n## Objective\n- Ship feature",
        "test_plan_md": "# Test Plan\n\n## Manual Validation\n- Run checks",
    }
    monkeypatch.setattr(
        llm_service,
        "_PROVIDER_INVOKERS",
        {**llm_service._PROVIDER_INVOKERS, "openai": _mock_invoker_returning(json.dumps(payload))},
    )

    output = llm_service.generate_plan("story", {"repo_tree": ["a.py"]}, _cfg(enabled=True))
    assert "Change Request" in output.change_request_md
    assert "Test Plan" in output.test_plan_md


def test_generate_plan_rejects_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        llm_service,
        "_PROVIDER_INVOKERS",
        {**llm_service._PROVIDER_INVOKERS, "openai": _mock_invoker_returning("not-json")},
    )

    with pytest.raises(llm_service.LLMServiceError, match="not valid JSON"):
        llm_service.generate_plan("story", {}, _cfg(enabled=True))


def test_generate_proposed_steps_validates_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "steps": [
            {
                "id": "step-1",
                "file": "featureflow/workflow/nodes.py",
                "intent": "add-logic",
                "reason": "Needed by story",
            }
        ]
    }
    monkeypatch.setattr(
        llm_service,
        "_PROVIDER_INVOKERS",
        {**llm_service._PROVIDER_INVOKERS, "openai": _mock_invoker_returning(json.dumps(payload))},
    )

    output = llm_service.generate_proposed_steps("story", "cr", "tp", {}, _cfg(enabled=True))
    assert len(output.steps) == 1
    assert output.steps[0].file == "featureflow/workflow/nodes.py"


def test_invoke_openai_requires_api_key() -> None:
    with pytest.raises(llm_service.LLMServiceError, match="Missing API key"):
        llm_service._invoke_openai(
            "prompt",
            {"story": "x"},
            {
                "api_key": "",
                "model": "gpt-4.1-mini",
                "timeout_seconds": 30,
                "temperature": 0,
            },
        )


def test_unsupported_provider_raises() -> None:
    with pytest.raises(llm_service.LLMServiceError, match="Unsupported LLM provider: unknown"):
        llm_service.generate_plan("story", {}, _cfg(provider="unknown"))


@pytest.mark.parametrize("provider", ["anthropic", "gemini"])
def test_missing_api_key_fails_for_anthropic_and_gemini(
    monkeypatch: pytest.MonkeyPatch, provider: str
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(llm_service.LLMServiceError, match="Missing API key"):
        llm_service.generate_plan("story", {}, _cfg(provider=provider, api_key=""))


def test_ollama_does_not_require_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    payload = {
        "change_request_md": "# Change Request\n\n## Objective\n- Ship feature",
        "test_plan_md": "# Test Plan\n\n## Manual Validation\n- Run checks",
    }
    monkeypatch.setattr(
        llm_service,
        "_PROVIDER_INVOKERS",
        {**llm_service._PROVIDER_INVOKERS, "ollama": _mock_invoker_returning(json.dumps(payload))},
    )
    output = llm_service.generate_plan("story", {"repo_tree": ["a.py"]}, _cfg(provider="ollama", api_key=""))
    assert "Change Request" in output.change_request_md


@pytest.mark.parametrize("provider", ["openai", "anthropic", "gemini", "ollama"])
def test_generate_plan_with_each_provider_returns_validated_output(
    monkeypatch: pytest.MonkeyPatch, provider: str
) -> None:
    payload = {
        "change_request_md": "# Change Request\n\n## Objective\n- Ship feature",
        "test_plan_md": "# Test Plan\n\n## Manual Validation\n- Run checks",
    }
    monkeypatch.setattr(
        llm_service,
        "_PROVIDER_INVOKERS",
        {**llm_service._PROVIDER_INVOKERS, provider: _mock_invoker_returning(json.dumps(payload))},
    )
    output = llm_service.generate_plan(
        "story", {"repo_tree": ["a.py"]}, _cfg(provider=provider, api_key="key" if provider != "ollama" else "")
    )
    assert "Change Request" in output.change_request_md
    assert "Test Plan" in output.test_plan_md


@pytest.mark.parametrize("provider", ["openai", "anthropic", "gemini", "ollama"])
def test_generate_proposed_steps_with_each_provider_returns_validated_output(
    monkeypatch: pytest.MonkeyPatch, provider: str
) -> None:
    payload = {
        "steps": [
            {"id": "step-1", "file": "featureflow/workflow/nodes.py", "intent": "add-logic", "reason": "Needed"}
        ]
    }
    monkeypatch.setattr(
        llm_service,
        "_PROVIDER_INVOKERS",
        {**llm_service._PROVIDER_INVOKERS, provider: _mock_invoker_returning(json.dumps(payload))},
    )
    output = llm_service.generate_proposed_steps(
        "story", "cr", "tp", {}, _cfg(provider=provider, api_key="key" if provider != "ollama" else "")
    )
    assert len(output.steps) == 1
    assert output.steps[0].file == "featureflow/workflow/nodes.py"
