from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

REQUIRED_TOP_LEVEL = ("project", "runs", "security")
DEFAULT_LLM_CONFIG = {
    "enabled": False,
    "provider": "openai",
    "model": "gpt-4.1-mini",
    "api_key": "",
    "timeout_seconds": 30,
    "temperature": 0.0,
    "max_repo_tree_entries": 250,
    "max_diff_chars": 12000,
    "max_key_file_chars": 6000,
}


def get_project_root() -> Path:
    """Project root (directory containing featureflow package, pyproject.toml)."""
    return Path(__file__).resolve().parents[1]


def load_config(path: str | None = None) -> dict:
    root = get_project_root()
    env_path = os.getenv("FEATUREFLOW_CONFIG_PATH")
    selected_path = path or env_path
    config_path = Path(selected_path) if selected_path else root / "featureflow.yaml"
    if not config_path.is_absolute():
        config_path = root / config_path
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    for key in REQUIRED_TOP_LEVEL:
        if key not in data:
            raise ValueError(f"Missing required config section: {key}")
    return data


def get_allowed_write_roots(cfg: dict) -> list[str]:
    roots: list[str] = []
    security = cfg.get("security", {}) if isinstance(cfg, dict) else {}
    configured = security.get("allowed_write_roots", [])
    if isinstance(configured, list):
        roots.extend(str(item) for item in configured)
    if "outputs" not in roots:
        roots.append("outputs")
    return roots


def _to_int(value: Any, default: int) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def get_llm_config(cfg: dict[str, Any]) -> dict[str, Any]:
    llm_cfg_raw = cfg.get("llm", {}) if isinstance(cfg, dict) else {}
    if not isinstance(llm_cfg_raw, dict):
        llm_cfg_raw = {}

    merged = dict(DEFAULT_LLM_CONFIG)
    merged.update(llm_cfg_raw)
    merged["enabled"] = bool(merged.get("enabled", False))
    merged["provider"] = str(merged.get("provider", DEFAULT_LLM_CONFIG["provider"])).strip() or DEFAULT_LLM_CONFIG[
        "provider"
    ]
    merged["model"] = str(merged.get("model", DEFAULT_LLM_CONFIG["model"])).strip() or DEFAULT_LLM_CONFIG["model"]
    merged["api_key"] = str(merged.get("api_key", "") or os.getenv("OPENAI_API_KEY", "") or "").strip()
    merged["timeout_seconds"] = max(1, _to_int(merged.get("timeout_seconds"), DEFAULT_LLM_CONFIG["timeout_seconds"]))
    merged["temperature"] = max(0.0, _to_float(merged.get("temperature"), DEFAULT_LLM_CONFIG["temperature"]))
    merged["max_repo_tree_entries"] = max(
        1,
        _to_int(merged.get("max_repo_tree_entries"), DEFAULT_LLM_CONFIG["max_repo_tree_entries"]),
    )
    merged["max_diff_chars"] = max(1, _to_int(merged.get("max_diff_chars"), DEFAULT_LLM_CONFIG["max_diff_chars"]))
    merged["max_key_file_chars"] = max(
        1,
        _to_int(merged.get("max_key_file_chars"), DEFAULT_LLM_CONFIG["max_key_file_chars"]),
    )
    return merged
