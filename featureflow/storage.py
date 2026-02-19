from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .run_state import RunStatus, coerce_status, is_valid_transition
from .time_utils import utc_now_iso

STATUS_CREATED = RunStatus.CREATED.value
STATUS_PLANNED = RunStatus.PLANNED.value
STATUS_WAITING_APPROVAL_PLAN = RunStatus.WAITING_APPROVAL_PLAN.value
STATUS_APPROVED_PLAN = RunStatus.APPROVED_PLAN.value
STATUS_PATCH_PROPOSED = RunStatus.PATCH_PROPOSED.value
STATUS_WAITING_APPROVAL_PATCH = RunStatus.WAITING_APPROVAL_PATCH.value
STATUS_APPROVED_PATCH = RunStatus.APPROVED_PATCH.value
STATUS_TESTS_RUNNING = RunStatus.TESTS_RUNNING.value
STATUS_TESTS_FAILED = RunStatus.TESTS_FAILED.value
STATUS_TESTS_PASSED = RunStatus.TESTS_PASSED.value
STATUS_WAITING_APPROVAL_FINAL = RunStatus.WAITING_APPROVAL_FINAL.value
STATUS_FINALIZED = RunStatus.FINALIZED.value
STATUS_FAILED = RunStatus.FAILED.value

GATE_PLAN = "plan"
GATE_PATCH = "patch"
GATE_FINAL = "final"

GATE_TRANSITIONS = {
    GATE_PLAN: (RunStatus.WAITING_APPROVAL_PLAN, RunStatus.APPROVED_PLAN),
    GATE_PATCH: (RunStatus.WAITING_APPROVAL_PATCH, RunStatus.APPROVED_PATCH),
    GATE_FINAL: (RunStatus.WAITING_APPROVAL_FINAL, RunStatus.FINALIZED),
}


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
        "status": STATUS_CREATED,
        "created_at": now,
        "updated_at": now,
        "inputs": inputs,
        "commands": [],
        "test_results": None,
        "approvals": [],
        "loop_iters": 0,
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


def _normalize_status(value: str | RunStatus) -> RunStatus:
    try:
        return coerce_status(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid status: {value!r}") from exc


def transition_status(
    run_id: str,
    outputs_dir: str,
    next_status: str | RunStatus,
    allowed_roots: list[str] | None = None,
) -> dict:
    data = read_run(run_id, outputs_dir)
    current_raw = data.get("status")
    current = _normalize_status(current_raw)
    target = _normalize_status(next_status)
    if not is_valid_transition(current, target):
        raise ValueError(f"Invalid transition: {current.value} -> {target.value}")

    if current == RunStatus.TESTS_FAILED and target == RunStatus.PATCH_PROPOSED:
        loop_iters = data.get("loop_iters", 0)
        if not isinstance(loop_iters, int):
            try:
                loop_iters = int(loop_iters)
            except (TypeError, ValueError):
                loop_iters = 0
        data["loop_iters"] = loop_iters + 1

    data["status"] = target.value
    write_run(run_id, outputs_dir, data, allowed_roots)
    return data


def update_status(
    run_id: str,
    outputs_dir: str,
    status: str,
    allowed_roots: list[str] | None = None,
) -> None:
    transition_status(run_id, outputs_dir, status, allowed_roots)


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
    current_status = _normalize_status(data.get("status"))
    if current_status != expected_status:
        raise ValueError(
            f"Cannot approve gate '{gate}' from status '{current_status.value}'. "
            f"Expected status '{expected_status.value}'."
        )

    approvals = data.get("approvals")
    if not isinstance(approvals, list):
        approvals = []
    approvals.append(
        {
            "gate": gate,
            "approved_at": utc_now_iso(),
            "approver": approver,
        }
    )
    data["approvals"] = approvals
    data["status"] = next_status.value
    write_run(run_id, outputs_dir, data, allowed_roots)
    return data
