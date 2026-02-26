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
            "max_repo_files_index_entries": 100,
            "max_diff_chars": 50,
            "max_key_file_chars": 20,
            "grounding_enabled": True,
            "grounding_min_touched_files": 4,
            "grounding_min_total_tests": 2,
            "grounding_require_convention_evidence": True,
        },
        "security": {
            "allowed_commands": [
                ["python", "-m", "pytest", "-q"],
                ["ruff", "check", "."],
            ]
        }
    }
    if overrides:
        llm_overrides = {k: v for k, v in overrides.items() if k in cfg["llm"]}
        sec_overrides = {k: v for k, v in overrides.items() if k in cfg["security"]}
        cfg["llm"].update(llm_overrides)
        cfg["security"].update(sec_overrides)
    return cfg


def _mock_invoker_returning(raw_json: str):
    def _invoker(_prompt: str, _payload: dict, _cfg: dict) -> str:
        return raw_json
    return _invoker


def _plan_payload() -> dict:
    return {
        "change_request_md": "# Change Request\n\n## Objective\n- Ship feature",
        "test_plan_md": "# Test Plan\n\n## Manual Validation\n- Run checks",
        "plan": {
            "touched_files": [
                {"path": "featureflow/workflow/nodes.py", "reason": "planner flow"},
                {"path": "featureflow/llm/service.py", "reason": "grounding"},
                {"path": "featureflow/llm/models.py", "reason": "output schema"},
                {"path": "tests/test_llm_service.py", "reason": "coverage"},
                {"path": "README.md", "reason": "conventions"},
            ],
            "proposed_edits": [
                {
                    "path": "featureflow/llm/service.py",
                    "change_summary": "add grounding checker",
                    "is_new": False,
                }
            ],
            "existing_tests": [{"path": "tests/test_llm_service.py", "why_relevant": "llm outputs"}],
            "new_tests": [{"path": "tests/test_workflow_llm_fallback.py", "what_it_validates": "persistence"}],
            "commands_to_run": ["python -m pytest -q"],
            "evidence": [{"path": "README.md", "excerpt_or_reason": "documents workflow"}],
        },
        "refusal": None,
    }


def _context() -> dict:
    return {
        "repo_tree": ["featureflow/", "tests/", "README.md"],
        "repo_files_index": [
            "featureflow/workflow/nodes.py",
            "featureflow/llm/service.py",
            "featureflow/llm/models.py",
            "tests/test_llm_service.py",
            "tests/test_workflow_llm_fallback.py",
            "README.md",
            "AGENTS.md",
        ],
        "key_files": {"README.md": "workflow docs"},
    }


def test_generate_plan_returns_validated_output(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _plan_payload()
    monkeypatch.setattr(
        llm_service,
        "_PROVIDER_INVOKERS",
        {**llm_service._PROVIDER_INVOKERS, "openai": _mock_invoker_returning(json.dumps(payload))},
    )

    output = llm_service.generate_plan("story", _context(), _cfg(enabled=True))
    assert "Change Request" in output.change_request_md
    assert "Test Plan" in output.test_plan_md
    assert output.plan is not None
    assert output.refusal is None


def test_generate_plan_rejects_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        llm_service,
        "_PROVIDER_INVOKERS",
        {**llm_service._PROVIDER_INVOKERS, "openai": _mock_invoker_returning("not-json")},
    )

    with pytest.raises(llm_service.LLMServiceError, match="not valid JSON"):
        llm_service.generate_plan("story", {}, _cfg(enabled=True))


def test_generate_plan_accepts_json_inside_code_fence_with_text_before(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LLM sometimes returns 'Here is the plan:\\n```json\\n{...}\\n```'; we extract the block."""
    payload = _plan_payload()
    wrapped = f"Here is the plan:\n```json\n{json.dumps(payload)}\n```"
    monkeypatch.setattr(
        llm_service,
        "_PROVIDER_INVOKERS",
        {**llm_service._PROVIDER_INVOKERS, "openai": _mock_invoker_returning(wrapped)},
    )
    output = llm_service.generate_plan("story", _context(), _cfg(enabled=True))
    assert output.plan is not None
    assert output.refusal is None


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
    payload = _plan_payload()
    monkeypatch.setattr(
        llm_service,
        "_PROVIDER_INVOKERS",
        {**llm_service._PROVIDER_INVOKERS, "ollama": _mock_invoker_returning(json.dumps(payload))},
    )
    output = llm_service.generate_plan("story", _context(), _cfg(provider="ollama", api_key=""))
    assert "Change Request" in output.change_request_md


@pytest.mark.parametrize("provider", ["openai", "anthropic", "gemini", "ollama"])
def test_generate_plan_with_each_provider_returns_validated_output(
    monkeypatch: pytest.MonkeyPatch, provider: str
) -> None:
    payload = _plan_payload()
    monkeypatch.setattr(
        llm_service,
        "_PROVIDER_INVOKERS",
        {**llm_service._PROVIDER_INVOKERS, provider: _mock_invoker_returning(json.dumps(payload))},
    )
    output = llm_service.generate_plan(
        "story",
        _context(),
        _cfg(provider=provider, api_key="key" if provider != "ollama" else ""),
    )
    assert "Change Request" in output.change_request_md
    assert "Test Plan" in output.test_plan_md
    assert output.plan is not None


def test_generate_plan_rejects_when_plan_and_refusal_are_both_set(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _plan_payload()
    payload["refusal"] = {
        "missing": ["tests"],
        "inspected_paths": ["featureflow/"],
        "message": "missing context",
    }
    monkeypatch.setattr(
        llm_service,
        "_PROVIDER_INVOKERS",
        {**llm_service._PROVIDER_INVOKERS, "openai": _mock_invoker_returning(json.dumps(payload))},
    )

    with pytest.raises(llm_service.LLMServiceError, match="Planner response validation failed"):
        llm_service.generate_plan("story", _context(), _cfg(enabled=True))


def test_generate_plan_converts_non_grounded_paths_to_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _plan_payload()
    payload["plan"]["touched_files"][0]["path"] = "does/not/exist.py"
    monkeypatch.setattr(
        llm_service,
        "_PROVIDER_INVOKERS",
        {**llm_service._PROVIDER_INVOKERS, "openai": _mock_invoker_returning(json.dumps(payload))},
    )
    output = llm_service.generate_plan("story", _context(), _cfg(enabled=True))
    assert output.plan is None
    assert output.refusal is not None
    assert "does/not/exist.py" in output.refusal.message


def test_generate_plan_converts_disallowed_commands_to_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _plan_payload()
    payload["plan"]["commands_to_run"] = ["python -m pip list"]
    monkeypatch.setattr(
        llm_service,
        "_PROVIDER_INVOKERS",
        {**llm_service._PROVIDER_INVOKERS, "openai": _mock_invoker_returning(json.dumps(payload))},
    )
    output = llm_service.generate_plan("story", _context(), _cfg(enabled=True))
    assert output.plan is None
    assert output.refusal is not None
    assert "not allowed" in output.refusal.message


def test_generate_plan_allows_new_files_in_proposed_edits(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _plan_payload()
    payload["plan"]["proposed_edits"] = [
        {
            "path": "tests/test_new_planner_grounding.py",
            "change_summary": "new tests",
            "is_new": True,
        }
    ]
    monkeypatch.setattr(
        llm_service,
        "_PROVIDER_INVOKERS",
        {**llm_service._PROVIDER_INVOKERS, "openai": _mock_invoker_returning(json.dumps(payload))},
    )
    output = llm_service.generate_plan("story", _context(), _cfg(enabled=True))
    assert output.plan is not None
    assert output.refusal is None


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
