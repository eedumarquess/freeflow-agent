from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

REQUIRED_TOP_LEVEL = ("project", "runs", "security")


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
