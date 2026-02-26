from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from featureflow.config import SUPPORTED_LLM_PROVIDERS, get_llm_config

from .models import PlannerOutput, ProposerOutput, RefusalPayload


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
    repo_files_index_raw = context_dict.get("repo_files_index")
    repo_files_index = repo_files_index_raw if isinstance(repo_files_index_raw, list) else []
    highlight_dirs_raw = context_dict.get("highlight_dirs")
    highlight_dirs = highlight_dirs_raw if isinstance(highlight_dirs_raw, list) else []
    constraints_raw = context_dict.get("constraints")
    constraints = constraints_raw if isinstance(constraints_raw, dict) else {}
    tests_summary = str(context_dict.get("tests_summary", "") or "")
    max_repo_tree_entries = int(cfg["max_repo_tree_entries"])
    max_repo_files_index_entries = int(cfg["max_repo_files_index_entries"])
    max_key_file_chars = int(cfg["max_key_file_chars"])
    max_diff_chars = int(cfg["max_diff_chars"])

    key_files_raw = context_dict.get("key_files")
    key_files: dict[str, str] = {}
    if isinstance(key_files_raw, dict):
        for key, value in key_files_raw.items():
            key_files[str(key)] = _truncate_text(value, max_key_file_chars)

    return {
        "repo_tree": [str(item) for item in repo_tree[:max_repo_tree_entries]],
        "repo_files_index": [str(item) for item in repo_files_index[:max_repo_files_index_entries]],
        "highlight_dirs": [str(item) for item in highlight_dirs],
        "tests_summary": _truncate_text(tests_summary, max_key_file_chars),
        "key_files": key_files,
        "constraints": constraints,
        "current_diff": _truncate_text(context_dict.get("current_diff", ""), max_diff_chars),
        "branch": context_dict.get("branch"),
        "base_branch": context_dict.get("base_branch"),
    }


def _normalize_command(raw: Any) -> str:
    if isinstance(raw, list):
        return " ".join(str(part).strip() for part in raw if str(part).strip())
    text = str(raw or "").strip()
    return " ".join(text.split())


def _build_grounding_refusal(
    reasons: list[str],
    inspected_paths: set[str],
    repo_files_index: set[str],
    change_request_md: str,
    test_plan_md: str,
) -> PlannerOutput:
    inspected = sorted(path for path in inspected_paths if path)
    if not inspected:
        inspected = sorted(repo_files_index)[:50]
    message = f"Grounding validation failed: {reasons[0]}" if reasons else "Grounding validation failed."
    return PlannerOutput(
        change_request_md=change_request_md,
        test_plan_md=test_plan_md,
        plan=None,
        refusal=RefusalPayload(
            missing=reasons,
            inspected_paths=inspected,
            message=message,
        ),
    )


def _apply_grounding_validation(
    output: PlannerOutput,
    context_dict: dict[str, Any],
    cfg: dict[str, Any],
    llm_cfg: dict[str, Any],
) -> PlannerOutput:
    if not llm_cfg.get("grounding_enabled", True):
        return output
    if output.refusal is not None:
        return output
    if output.plan is None:
        return output

    repo_files_index_raw = context_dict.get("repo_files_index")
    repo_files_index_list = repo_files_index_raw if isinstance(repo_files_index_raw, list) else []
    repo_files_index = {str(path) for path in repo_files_index_list if str(path).strip()}
    convention_docs = {"AGENTS.md", "README.md", "CONTRIBUTING.md"} & repo_files_index

    reasons: list[str] = []
    inspected_paths: set[str] = set()
    plan = output.plan

    for item in plan.touched_files:
        inspected_paths.add(item.path)
        if item.path not in repo_files_index:
            reasons.append(f"touched_files path not found: {item.path}")

    for item in plan.existing_tests:
        inspected_paths.add(item.path)
        if item.path not in repo_files_index:
            reasons.append(f"existing_tests path not found: {item.path}")

    for item in plan.evidence:
        inspected_paths.add(item.path)
        if item.path not in repo_files_index:
            reasons.append(f"evidence path not found: {item.path}")

    for item in plan.proposed_edits:
        inspected_paths.add(item.path)
        if not item.is_new and item.path not in repo_files_index:
            reasons.append(f"proposed_edits path not found and is_new is false: {item.path}")

    min_touched = int(llm_cfg.get("grounding_min_touched_files", 4))
    if len(plan.touched_files) < min_touched:
        reasons.append(f"touched_files count below minimum ({len(plan.touched_files)} < {min_touched})")

    min_total_tests = int(llm_cfg.get("grounding_min_total_tests", 2))
    total_tests = len(plan.existing_tests) + len(plan.new_tests)
    if total_tests < min_total_tests:
        reasons.append(f"total planned tests below minimum ({total_tests} < {min_total_tests})")

    require_convention_evidence = bool(llm_cfg.get("grounding_require_convention_evidence", True))
    if require_convention_evidence and convention_docs:
        evidence_paths = {item.path for item in plan.evidence}
        key_files_keys = set(context_dict.get("key_files") or [])
        # Satisfied if plan cites a convention doc in evidence, or context included one in key_files (LLM had it)
        has_evidence = bool(evidence_paths & convention_docs) or bool(key_files_keys & convention_docs)
        if not has_evidence:
            docs = ", ".join(sorted(convention_docs))
            reasons.append(f"evidence must include at least one convention doc ({docs})")

    allowed_commands_raw = cfg.get("security", {}).get("allowed_commands", []) if isinstance(cfg, dict) else []
    allowed_commands = {_normalize_command(cmd) for cmd in allowed_commands_raw}
    for command in plan.commands_to_run:
        normalized = _normalize_command(command)
        if not normalized:
            reasons.append("commands_to_run contains an empty command")
            continue
        if normalized not in allowed_commands:
            reasons.append(f"commands_to_run command is not allowed: {normalized}")

    if reasons:
        return _build_grounding_refusal(
            reasons=reasons,
            inspected_paths=inspected_paths,
            repo_files_index=repo_files_index,
            change_request_md=output.change_request_md,
            test_plan_md=output.test_plan_md,
        )
    return output


def _extract_json_from_code_fence(raw: str) -> str | None:
    """Extract JSON from a markdown code block. Matches whole-string or first block in text."""
    text = raw.strip()
    # Whole string is a single code block
    match = re.match(r"^```(?:json)?\s*\n?(.*?)\s*```\s*$", text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    # First code block anywhere in the response (LLM added text before/after)
    search = re.search(r"```(?:json)?\s*\n?(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if search:
        return search.group(1).strip()
    return None


def _truncate_for_error(text: str, max_chars: int = 200) -> str:
    """Return a safe one-line preview for error messages."""
    one = " ".join(text.split())
    if len(one) <= max_chars:
        return one
    return one[:max_chars] + "..."


def _parse_json_object(raw_text: str) -> dict[str, Any]:
    payload_text = raw_text.strip()
    if not payload_text:
        raise LLMServiceError("LLM returned empty response")

    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as first_err:
        fenced = _extract_json_from_code_fence(payload_text)
        if not fenced:
            preview = _truncate_for_error(payload_text)
            raise LLMServiceError(
                f"LLM response is not valid JSON (no JSON object or code block). Preview: {preview!r}"
            ) from first_err
        try:
            payload = json.loads(fenced)
        except json.JSONDecodeError as exc:
            raise LLMServiceError(
                f"LLM response inside code fence is not valid JSON: line {exc.lineno} col {exc.colno} — {exc.msg}"
            ) from exc

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


def _system_instruction() -> str:
    return "Return only valid JSON with no extra text."


def _build_messages(prompt: str, input_payload: dict[str, Any]) -> list:
    """Build [system, human] messages for any provider (LangChain message types)."""
    request_json = json.dumps(input_payload, ensure_ascii=True, indent=2)
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
    except Exception as exc:
        raise LLMServiceError("langchain_core messages not available") from exc
    return [
        SystemMessage(content=_system_instruction()),
        HumanMessage(content=f"{prompt}\n\nInput JSON:\n{request_json}"),
    ]


def _invoke_openai(prompt: str, input_payload: dict[str, Any], llm_cfg: dict[str, Any]) -> str:
    api_key = str(llm_cfg.get("api_key") or "").strip()
    if not api_key:
        raise LLMServiceError("Missing API key: set llm.api_key or OPENAI_API_KEY")

    try:
        from langchain_openai import ChatOpenAI
    except Exception as exc:
        raise LLMServiceError("langchain-openai is not available") from exc

    model_name = str(llm_cfg.get("model", "gpt-4.1-mini"))
    timeout_seconds = int(llm_cfg.get("timeout_seconds", 30))
    temperature = float(llm_cfg.get("temperature", 0.0))
    client = ChatOpenAI(
        model=model_name,
        temperature=temperature,
        timeout=timeout_seconds,
        api_key=api_key,
    )
    response = client.invoke(_build_messages(prompt, input_payload))
    return _response_to_text(response)


def _invoke_anthropic(prompt: str, input_payload: dict[str, Any], llm_cfg: dict[str, Any]) -> str:
    api_key = str(llm_cfg.get("api_key") or "").strip()
    if not api_key:
        raise LLMServiceError("Missing API key: set llm.api_key or ANTHROPIC_API_KEY")

    try:
        from langchain_anthropic import ChatAnthropic
    except Exception as exc:
        raise LLMServiceError("langchain-anthropic is not available") from exc

    model_name = str(llm_cfg.get("model", "claude-3-5-haiku-20241022"))
    timeout_seconds = int(llm_cfg.get("timeout_seconds", 30))
    temperature = float(llm_cfg.get("temperature", 0.0))
    client = ChatAnthropic(
        model=model_name,
        temperature=temperature,
        timeout=timeout_seconds,
        api_key=api_key,
    )
    response = client.invoke(_build_messages(prompt, input_payload))
    return _response_to_text(response)


def _invoke_gemini(prompt: str, input_payload: dict[str, Any], llm_cfg: dict[str, Any]) -> str:
    api_key = str(llm_cfg.get("api_key") or "").strip()
    if not api_key:
        raise LLMServiceError("Missing API key: set llm.api_key or GOOGLE_API_KEY / GEMINI_API_KEY")

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except Exception as exc:
        raise LLMServiceError("langchain-google-genai is not available") from exc

    model_name = str(llm_cfg.get("model", "gemini-2.0-flash"))
    timeout_seconds = int(llm_cfg.get("timeout_seconds", 30))
    temperature = float(llm_cfg.get("temperature", 0.0))
    client = ChatGoogleGenerativeAI(
        model=model_name,
        temperature=temperature,
        timeout=timeout_seconds,
        api_key=api_key,
    )
    response = client.invoke(_build_messages(prompt, input_payload))
    return _response_to_text(response)


def _invoke_ollama(prompt: str, input_payload: dict[str, Any], llm_cfg: dict[str, Any]) -> str:
    base_url = str(llm_cfg.get("base_url") or "").strip()
    if not base_url:
        base_url = "http://localhost:11434"

    try:
        from langchain_ollama import ChatOllama
    except Exception as exc:
        raise LLMServiceError("langchain-ollama is not available") from exc

    model_name = str(llm_cfg.get("model", "llama3.2"))
    timeout_seconds = int(llm_cfg.get("timeout_seconds", 30))
    temperature = float(llm_cfg.get("temperature", 0.0))
    client = ChatOllama(
        model=model_name,
        temperature=temperature,
        base_url=base_url,
        timeout=timeout_seconds,
    )
    response = client.invoke(_build_messages(prompt, input_payload))
    return _response_to_text(response)


_PROVIDER_INVOKERS: dict[str, Callable[..., str]] = {
    "openai": _invoke_openai,
    "anthropic": _invoke_anthropic,
    "gemini": _invoke_gemini,
    "ollama": _invoke_ollama,
}


def _invoke_llm(prompt_name: str, input_payload: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    llm_cfg = get_llm_config(cfg)
    if not llm_cfg["enabled"]:
        raise LLMServiceError("LLM is disabled")

    provider = str(llm_cfg.get("provider", "openai")).strip().lower()
    if provider not in SUPPORTED_LLM_PROVIDERS:
        raise LLMServiceError(f"Unsupported LLM provider: {provider}")

    invoker = _PROVIDER_INVOKERS.get(provider)
    if not invoker:
        raise LLMServiceError(f"Unsupported LLM provider: {provider}")

    prompt = _read_prompt(prompt_name)
    raw = invoker(prompt, input_payload, llm_cfg)
    return _parse_json_object(raw)


def generate_plan(story: str, context_dict: dict[str, Any], cfg: dict[str, Any]) -> PlannerOutput:
    llm_cfg = get_llm_config(cfg)
    input_payload = {
        "story": story,
        "context": _build_context_payload(context_dict, llm_cfg),
    }
    raw = _invoke_llm("planner.md", input_payload, cfg)
    try:
        validated = PlannerOutput.model_validate(raw)
    except ValidationError as exc:
        raise LLMServiceError(f"Planner response validation failed: {exc}") from exc
    return _apply_grounding_validation(validated, context_dict, cfg, llm_cfg)


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
