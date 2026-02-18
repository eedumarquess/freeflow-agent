from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .time_utils import utc_now_iso


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def validate_write_path(path: Path, allowed_roots: list[str]) -> None:
    path = path.resolve()
    repo_root = _repo_root()
    for root in allowed_roots:
        root_path = (repo_root / root).resolve()
        if path == root_path or _is_relative_to(path, root_path):
            return
    raise PermissionError(f"Write path not allowed: {path}")


def ensure_run_dir(run_id: str, outputs_dir: str, allowed_roots: list[str] | None = None) -> Path:
    outputs_path = Path(outputs_dir) / run_id
    roots = allowed_roots or ["outputs"]
    validate_write_path(outputs_path, roots)
    outputs_path.mkdir(parents=True, exist_ok=True)
    return outputs_path


def _atomic_write_json(path: Path, data: dict) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def init_run(run_id: str, inputs: dict, outputs_dir: str, allowed_roots: list[str] | None = None) -> dict:
    run_dir = ensure_run_dir(run_id, outputs_dir, allowed_roots)
    run_path = run_dir / "run.json"
    if run_path.exists():
        raise FileExistsError(f"Run already exists: {run_id}")
    now = utc_now_iso()
    data = {
        "run_id": run_id,
        "status": "started",
        "created_at": now,
        "updated_at": now,
        "inputs": inputs,
        "commands": [],
        "test_results": None,
    }
    _atomic_write_json(run_path, data)
    return data


def read_run(run_id: str, outputs_dir: str) -> dict:
    run_path = Path(outputs_dir) / run_id / "run.json"
    return json.loads(run_path.read_text(encoding="utf-8"))


def write_run(run_id: str, outputs_dir: str, data: dict, allowed_roots: list[str] | None = None) -> None:
    run_path = Path(outputs_dir) / run_id / "run.json"
    roots = allowed_roots or ["outputs"]
    validate_write_path(run_path, roots)
    data["updated_at"] = utc_now_iso()
    _atomic_write_json(run_path, data)


def append_command(
    run_id: str,
    outputs_dir: str,
    cmd_result: dict,
    allowed_roots: list[str] | None = None,
) -> None:
    data = read_run(run_id, outputs_dir)
    commands = data.get("commands")
    if not isinstance(commands, list):
        commands = []
    commands.append(cmd_result)
    data["commands"] = commands
    write_run(run_id, outputs_dir, data, allowed_roots)


def update_status(run_id: str, outputs_dir: str, status: str) -> None:
    data = read_run(run_id, outputs_dir)
    data["status"] = status
    write_run(run_id, outputs_dir, data)
