from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REQUIRED_TOP_LEVEL = ("project", "runs", "security")


def load_config(path: str = "featureflow.yaml") -> dict:
    config_path = Path(path)
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
