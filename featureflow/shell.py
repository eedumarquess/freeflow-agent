from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .storage import append_command
from .time_utils import utc_now_iso


def run_command(
    cmd: list[str],
    allowed_commands: list[list[str]],
    run_id: str | None,
    outputs_dir: str,
    timeout_seconds: int,
    cwd: Path | str | None = None,
    allowed_write_roots: list[str] | None = None,
) -> dict:
    if cmd not in allowed_commands:
        raise PermissionError(f"Command not allowed: {cmd}")

    started_at = utc_now_iso()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            shell=False,
            cwd=cwd,
        )
        finished_at = utc_now_iso()
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
        finished_at = utc_now_iso()
        record = {
            "command": cmd,
            "started_at": started_at,
            "finished_at": finished_at,
            "exit_code": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or f"Command timed out after {timeout_seconds}s",
            "timeout_seconds": timeout_seconds,
        }

    if run_id is not None:
        append_command(run_id, outputs_dir, record, allowed_write_roots)
    return record
