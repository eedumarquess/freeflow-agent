from __future__ import annotations

import sys
import tempfile

import pytest

from featureflow.storage import init_run
from featureflow.shell import run_command


def test_allowed_command_executes_successfully() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        run_id = "test_run"
        outputs_dir = tmpdir
        allowed_roots = [tmpdir]
        init_run(run_id, {"story": "test"}, outputs_dir, allowed_roots)

        cmd = [sys.executable, "-c", "print('ok')"]
        result = run_command(
            cmd,
            [cmd],
            run_id,
            outputs_dir,
            timeout_seconds=10,
            allowed_write_roots=allowed_roots,
        )

        assert result["exit_code"] == 0
        assert "ok" in result["stdout"]


def test_disallowed_command_fails() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        run_id = "test_run"
        outputs_dir = tmpdir
        allowed_roots = [tmpdir]
        init_run(run_id, {"story": "test"}, outputs_dir, allowed_roots)

        with pytest.raises(PermissionError):
            run_command(
                ["echo", "nope"],
                [["python", "-c", "print('ok')"]],
                run_id,
                outputs_dir,
                timeout_seconds=10,
            )
