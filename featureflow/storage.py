from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

STATUS_CREATED = "CREATED"
STATUS_PLANNED = "PLANNED"
STATUS_WAITING_APPROVAL_PLAN = "WAITING_APPROVAL_PLAN"
STATUS_APPROVED_PLAN = "APPROVED_PLAN"
STATUS_PATCH_PROPOSED = "PATCH_PROPOSED"
STATUS_WAITING_APPROVAL_PATCH = "WAITING_APPROVAL_PATCH"
STATUS_APPROVED_PATCH = "APPROVED_PATCH"
STATUS_TESTS_RUNNING = "TESTS_RUNNING"
STATUS_TESTS_FAILED = "TESTS_FAILED"
STATUS_TESTS_PASSED = "TESTS_PASSED"
STATUS_WAITING_APPROVAL_FINAL = "WAITING_APPROVAL_FINAL"
STATUS_FINALIZED = "FINALIZED"
STATUS_FAILED = "FAILED"

GATE_PLAN = "plan"
GATE_PATCH = "patch"
GATE_FINAL = "final"

GATE_TRANSITIONS = {
    GATE_PLAN: (STATUS_WAITING_APPROVAL_PLAN, STATUS_APPROVED_PLAN),
    GATE_PATCH: (STATUS_WAITING_APPROVAL_PATCH, STATUS_APPROVED_PATCH),
    GATE_FINAL: (STATUS_WAITING_APPROVAL_FINAL, STATUS_FINALIZED),
}


def _utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


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
    now = _utc_now_iso()
    data = {
        "run_id": run_id,
        "status": STATUS_CREATED,
        "created_at": now,
        "updated_at": now,
        "inputs": inputs,
        "commands": [],
        "test_results": None,
        "approvals": [],
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
    data["updated_at"] = _utc_now_iso()
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


def update_status(
    run_id: str,
    outputs_dir: str,
    status: str,
    allowed_roots: list[str] | None = None,
) -> None:
    data = read_run(run_id, outputs_dir)
    data["status"] = status
    write_run(run_id, outputs_dir, data, allowed_roots)


def approve_gate(
    run_id: str,
    outputs_dir: str,
    gate: str,
    approver: str = "local",
    allowed_roots: list[str] | None = None,
) -> dict:
    if gate not in GATE_TRANSITIONS:
        valid = ", ".join(sorted(GATE_TRANSITIONS.keys()))
        raise ValueError(f"Invalid gate '{gate}'. Expected one of: {valid}")

    expected_status, next_status = GATE_TRANSITIONS[gate]
    data = read_run(run_id, outputs_dir)
    current_status = data.get("status")
    if current_status != expected_status:
        raise ValueError(
            f"Cannot approve gate '{gate}' from status '{current_status}'. "
            f"Expected status '{expected_status}'."
        )

    approvals = data.get("approvals")
    if not isinstance(approvals, list):
        approvals = []
    approvals.append(
        {
            "gate": gate,
            "approved_at": _utc_now_iso(),
            "approver": approver,
        }
    )
    data["approvals"] = approvals
    data["status"] = next_status
    write_run(run_id, outputs_dir, data, allowed_roots)
    return data
