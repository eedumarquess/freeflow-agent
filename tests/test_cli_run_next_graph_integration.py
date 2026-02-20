from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

import cli.main as cli_main
from featureflow.storage import (
    STATUS_FINALIZED,
    STATUS_WAITING_APPROVAL_FINAL,
    STATUS_WAITING_APPROVAL_PATCH,
    STATUS_WAITING_APPROVAL_PLAN,
    read_run,
)


def _write_cfg(path: Path, outputs_dir: Path, allowed_root: Path) -> None:
    cfg = f"""
project:
  base_branch: "main"
runs:
  outputs_dir: "{outputs_dir.as_posix()}"
  max_iters: 2
  timeout_seconds: 60
security:
  allowed_commands:
    - ["pytest", "-q"]
  allowed_write_roots:
    - "{allowed_root.as_posix()}"
  fs_ops:
    max_file_bytes: 524288
    max_diff_lines: 800
    max_files_changed: 20
""".lstrip()
    path.write_text(cfg, encoding="utf-8")


def test_run_next_flow_uses_graph_and_stops_at_gates(tmp_path: Path, monkeypatch) -> None:
    outputs_dir = tmp_path / "outputs" / "runs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = tmp_path / "featureflow.yaml"
    _write_cfg(cfg_path, outputs_dir, tmp_path)

    monkeypatch.setenv("FEATUREFLOW_CONFIG_PATH", str(cfg_path))
    monkeypatch.setattr(cli_main, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(cli_main, "generate_run_id", lambda: "run_graph_001")

    import featureflow.workflow.nodes as wf_nodes

    monkeypatch.setattr(wf_nodes, "ensure_agent_branch", lambda _run_id, _repo: "agent/run_graph_001")

    def _fake_run_command(*_args, **_kwargs):
        return {"command": ["pytest", "-q"], "exit_code": 0, "stdout": "ok", "stderr": ""}

    monkeypatch.setattr(wf_nodes, "run_command", _fake_run_command)

    runner = CliRunner()
    run_result = runner.invoke(cli_main.app, ["run", "Graph flow"])
    assert run_result.exit_code == 0
    run_data = read_run("run_graph_001", str(outputs_dir))
    assert run_data["status"] == STATUS_WAITING_APPROVAL_PLAN

    approve_plan = runner.invoke(
        cli_main.app, ["approve", "--run-id", "run_graph_001", "--gate", "plan"]
    )
    assert approve_plan.exit_code == 0
    next_after_plan = runner.invoke(cli_main.app, ["next", "--run-id", "run_graph_001"])
    assert next_after_plan.exit_code == 0
    run_data = read_run("run_graph_001", str(outputs_dir))
    assert run_data["status"] == STATUS_WAITING_APPROVAL_PATCH

    approve_patch = runner.invoke(
        cli_main.app, ["approve", "--run-id", "run_graph_001", "--gate", "patch"]
    )
    assert approve_patch.exit_code == 0
    next_after_patch = runner.invoke(cli_main.app, ["next", "--run-id", "run_graph_001"])
    assert next_after_patch.exit_code == 0
    run_data = read_run("run_graph_001", str(outputs_dir))
    assert run_data["status"] == STATUS_WAITING_APPROVAL_FINAL
    run_report = (outputs_dir / "run_graph_001" / "run-report.md").read_text(encoding="utf-8")
    assert "Node RUN_TESTS" in run_report
    assert "Stdout:\nok" in run_report
    assert "Stderr:\n" in run_report
    assert "## Command Log: `pytest -q`" in run_report

    approve_final = runner.invoke(
        cli_main.app, ["approve", "--run-id", "run_graph_001", "--gate", "final"]
    )
    assert approve_final.exit_code == 0
    next_after_final = runner.invoke(cli_main.app, ["next", "--run-id", "run_graph_001"])
    assert next_after_final.exit_code == 0
    run_data = read_run("run_graph_001", str(outputs_dir))
    assert run_data["status"] == STATUS_FINALIZED
    assert (outputs_dir / "run_graph_001" / "pr-comment.md").exists()
    assert (outputs_dir / "run_graph_001" / "metrics.json").exists()
    telemetry = run_data.get("telemetry")
    assert isinstance(telemetry, dict)
    node_events = telemetry.get("node_events")
    assert isinstance(node_events, list)
    assert node_events
    assert all(event.get("duration_sec", 0) >= 0 for event in node_events)
