from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from featureflow.config import get_llm_config

from .models import PlannerOutput, ProposerOutput


class LLMServiceError(RuntimeError):
    pass


def _prompts_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "prompts"


def _read_prompt(prompt_name: str) -> str:
    path = _prompts_dir() / prompt_name
    if not path.exists():
        raise LLMServiceError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def _truncate_text(value: Any, max_chars: int) -> str:
    text = str(value or "")
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


def _build_context_payload(context_dict: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    repo_tree_raw = context_dict.get("repo_tree")
    repo_tree = repo_tree_raw if isinstance(repo_tree_raw, list) else []
    max_repo_tree_entries = int(cfg["max_repo_tree_entries"])
    max_key_file_chars = int(cfg["max_key_file_chars"])
    max_diff_chars = int(cfg["max_diff_chars"])

    key_files_raw = context_dict.get("key_files")
    key_files: dict[str, str] = {}
    if isinstance(key_files_raw, dict):
        for key, value in key_files_raw.items():
            key_files[str(key)] = _truncate_text(value, max_key_file_chars)

    return {
        "repo_tree": [str(item) for item in repo_tree[:max_repo_tree_entries]],
        "key_files": key_files,
        "current_diff": _truncate_text(context_dict.get("current_diff", ""), max_diff_chars),
        "branch": context_dict.get("branch"),
        "base_branch": context_dict.get("base_branch"),
    }


def _extract_json_from_code_fence(raw: str) -> str | None:
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", raw.strip(), flags=re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()


def _parse_json_object(raw_text: str) -> dict[str, Any]:
    payload_text = raw_text.strip()
    if not payload_text:
        raise LLMServiceError("LLM returned empty response")

    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        fenced = _extract_json_from_code_fence(payload_text)
        if not fenced:
            raise LLMServiceError("LLM response is not valid JSON")
        try:
            payload = json.loads(fenced)
        except json.JSONDecodeError as exc:
            raise LLMServiceError("LLM response inside code fence is not valid JSON") from exc

    if not isinstance(payload, dict):
        raise LLMServiceError("LLM response JSON must be an object")
    return payload


def _response_to_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
                    continue
            parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def _invoke_openai(prompt: str, input_payload: dict[str, Any], llm_cfg: dict[str, Any]) -> str:
    api_key_env = str(llm_cfg.get("api_key_env", "OPENAI_API_KEY"))
    api_key = os.getenv(api_key_env, "").strip()
    if not api_key:
        raise LLMServiceError(f"Missing API key in env var: {api_key_env}")

    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_openai import ChatOpenAI
    except Exception as exc:  # pragma: no cover - depends on runtime environment
        raise LLMServiceError("langchain-openai is not available") from exc

    model_name = str(llm_cfg.get("model", "gpt-4.1-mini"))
    timeout_seconds = int(llm_cfg.get("timeout_seconds", 30))
    temperature = float(llm_cfg.get("temperature", 0.0))
    request_json = json.dumps(input_payload, ensure_ascii=True, indent=2)
    messages = [
        SystemMessage(content="Return only valid JSON with no extra text."),
        HumanMessage(content=f"{prompt}\n\nInput JSON:\n{request_json}"),
    ]
    client = ChatOpenAI(
        model=model_name,
        temperature=temperature,
        timeout=timeout_seconds,
        api_key=api_key,
    )
    response = client.invoke(messages)
    return _response_to_text(response)


def _invoke_llm(prompt_name: str, input_payload: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    llm_cfg = get_llm_config(cfg)
    if not llm_cfg["enabled"]:
        raise LLMServiceError("LLM is disabled")

    provider = str(llm_cfg.get("provider", "openai")).strip().lower()
    if provider != "openai":
        raise LLMServiceError(f"Unsupported LLM provider: {provider}")

    prompt = _read_prompt(prompt_name)
    raw = _invoke_openai(prompt, input_payload, llm_cfg)
    return _parse_json_object(raw)


def generate_plan(story: str, context_dict: dict[str, Any], cfg: dict[str, Any]) -> PlannerOutput:
    input_payload = {
        "story": story,
        "context": _build_context_payload(context_dict, get_llm_config(cfg)),
    }
    raw = _invoke_llm("planner.md", input_payload, cfg)
    try:
        return PlannerOutput.model_validate(raw)
    except ValidationError as exc:
        raise LLMServiceError(f"Planner response validation failed: {exc}") from exc


def generate_proposed_steps(
    story: str,
    change_request_md: str,
    test_plan_md: str,
    context_dict: dict[str, Any],
    cfg: dict[str, Any],
) -> ProposerOutput:
    input_payload = {
        "story": story,
        "change_request_md": change_request_md,
        "test_plan_md": test_plan_md,
        "context": _build_context_payload(context_dict, get_llm_config(cfg)),
    }
    raw = _invoke_llm("proposer.md", input_payload, cfg)
    try:
        return ProposerOutput.model_validate(raw)
    except ValidationError as exc:
        raise LLMServiceError(f"Proposer response validation failed: {exc}") from exc
