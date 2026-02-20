from __future__ import annotations

from pathlib import Path

from featureflow.artifacts import append_command_logs_to_run_report, create_run_artifacts
from featureflow.storage import append_command, init_run, read_run
from featureflow.workflow.nodes import NodeContext, finalize_node


def _cfg(outputs_dir: Path, allowed_root: Path) -> dict:
    return {
        "project": {"base_branch": "main"},
        "runs": {"outputs_dir": outputs_dir.as_posix(), "max_iters": 2, "timeout_seconds": 60},
        "security": {
            "allowed_commands": [["pytest", "-q"]],
            "allowed_write_roots": [allowed_root.as_posix()],
            "fs_ops": {"max_file_bytes": 524288, "max_diff_lines": 800, "max_files_changed": 20},
        },
    }


def test_finalize_reconciles_all_command_logs_into_run_report(tmp_path: Path) -> None:
    outputs_dir = tmp_path / "outputs" / "runs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    run_id = "run_finalize_logs"
    init_run(run_id, {"story": "finalize logs"}, str(outputs_dir), [str(tmp_path)])
    create_run_artifacts(run_id, str(outputs_dir), [str(tmp_path)])

    append_command(
        run_id,
        str(outputs_dir),
        {
            "command": ["pytest", "-q"],
            "started_at": "2026-02-20T10:00:00Z",
            "finished_at": "2026-02-20T10:00:05Z",
            "exit_code": 1,
            "stdout": "failed out",
            "stderr": "failed err",
            "timeout_seconds": 60,
        },
        [str(tmp_path)],
    )
    append_command(
        run_id,
        str(outputs_dir),
        {
            "command": ["pytest", "-q"],
            "started_at": "2026-02-20T10:01:00Z",
            "finished_at": "2026-02-20T10:01:07Z",
            "exit_code": 0,
            "stdout": "ok out",
            "stderr": "",
            "timeout_seconds": 60,
        },
        [str(tmp_path)],
    )

    ctx = NodeContext(
        cfg=_cfg(outputs_dir, tmp_path),
        repo_root=tmp_path,
        outputs_dir=str(outputs_dir),
        allowed_roots=[str(tmp_path)],
    )
    run_data = read_run(run_id, str(outputs_dir))
    finalize_node(run_data, ctx)

    report = (outputs_dir / run_id / "run-report.md").read_text(encoding="utf-8")
    assert report.count("## Command Log: `pytest -q`") == 2
    assert "Stdout:\nfailed out" in report
    assert "Stderr:\nfailed err" in report
    assert "Stdout:\nok out" in report

    # Reconciliation must be idempotent.
    assert append_command_logs_to_run_report(run_id, str(outputs_dir), [str(tmp_path)]) == 0
