from __future__ import annotations

import json

import pytest

import featureflow.llm.service as llm_service


def _cfg(enabled: bool = True) -> dict:
    return {
        "llm": {
            "enabled": enabled,
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "api_key_env": "OPENAI_API_KEY",
            "timeout_seconds": 30,
            "temperature": 0,
            "max_repo_tree_entries": 10,
            "max_diff_chars": 50,
            "max_key_file_chars": 20,
        }
    }


def test_generate_plan_returns_validated_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        llm_service,
        "_invoke_openai",
        lambda *_args, **_kwargs: json.dumps(
            {
                "change_request_md": "# Change Request\n\n## Objective\n- Ship feature",
                "test_plan_md": "# Test Plan\n\n## Manual Validation\n- Run checks",
            }
        ),
    )

    output = llm_service.generate_plan("story", {"repo_tree": ["a.py"]}, _cfg(enabled=True))
    assert "Change Request" in output.change_request_md
    assert "Test Plan" in output.test_plan_md


def test_generate_plan_rejects_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_service, "_invoke_openai", lambda *_args, **_kwargs: "not-json")

    with pytest.raises(llm_service.LLMServiceError, match="not valid JSON"):
        llm_service.generate_plan("story", {}, _cfg(enabled=True))


def test_generate_proposed_steps_validates_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        llm_service,
        "_invoke_openai",
        lambda *_args, **_kwargs: json.dumps(
            {
                "steps": [
                    {
                        "id": "step-1",
                        "file": "featureflow/workflow/nodes.py",
                        "intent": "add-logic",
                        "reason": "Needed by story",
                    }
                ]
            }
        ),
    )

    output = llm_service.generate_proposed_steps("story", "cr", "tp", {}, _cfg(enabled=True))
    assert len(output.steps) == 1
    assert output.steps[0].file == "featureflow/workflow/nodes.py"


def test_invoke_openai_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FEATUREFLOW_TEST_MISSING_KEY", raising=False)
    with pytest.raises(llm_service.LLMServiceError, match="Missing API key"):
        llm_service._invoke_openai(
            "prompt",
            {"story": "x"},
            {
                "api_key_env": "FEATUREFLOW_TEST_MISSING_KEY",
                "model": "gpt-4.1-mini",
                "timeout_seconds": 30,
                "temperature": 0,
            },
        )
