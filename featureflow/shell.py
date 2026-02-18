from __future__ import annotations

from datetime import datetime
import subprocess
from typing import Any

from .storage import append_command


def _utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def run_command(
    cmd: list[str],
    allowed_commands: list[list[str]],
    run_id: str,
    outputs_dir: str,
    timeout_seconds: int,
) -> dict:
    if cmd not in allowed_commands:
        raise PermissionError(f"Command not allowed: {cmd}")

    started_at = _utc_now_iso()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            shell=False,
        )
        finished_at = _utc_now_iso()
        record = {
            "command": cmd,
            "started_at": started_at,
            "finished_at": finished_at,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timeout_seconds": timeout_seconds,
        }
    except subprocess.TimeoutExpired as exc:
        finished_at = _utc_now_iso()
        record = {
            "command": cmd,
            "started_at": started_at,
            "finished_at": finished_at,
            "exit_code": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or f"Command timed out after {timeout_seconds}s",
            "timeout_seconds": timeout_seconds,
        }

    append_command(run_id, outputs_dir, record)
    return record
