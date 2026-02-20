from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

import cli.main as cli_main
from featureflow.storage import (
    STATUS_APPROVED_PATCH,
    STATUS_APPROVED_PLAN,
    STATUS_FINALIZED,
    STATUS_PATCH_PROPOSED,
    STATUS_PLANNED,
    STATUS_TESTS_FAILED,
    STATUS_TESTS_PASSED,
    STATUS_TESTS_RUNNING,
    STATUS_WAITING_APPROVAL_FINAL,
    STATUS_WAITING_APPROVAL_PATCH,
    STATUS_WAITING_APPROVAL_PLAN,
    init_run,
    read_run,
    update_status,
    write_run,
)
from featureflow.artifacts import create_run_artifacts


def _write_cfg(path: Path, outputs_dir: Path, allowed_root: Path) -> None:
    cfg = f"""
project:
  base_branch: "main"
runs:
  outputs_dir: "{outputs_dir.as_posix()}"
  max_iters: 1
  timeout_seconds: 60
security:
  allowed_commands: []
  allowed_write_roots:
    - "{allowed_root.as_posix()}"
""".lstrip()
    path.write_text(cfg, encoding="utf-8")


def _advance_status(
    run_id: str, outputs_dir: Path, allowed_root: Path, statuses: list[str]
) -> None:
    for status in statuses:
        update_status(run_id, str(outputs_dir), status, [str(allowed_root)])


def test_run_pauses_waiting_plan_and_prints_instruction(tmp_path: Path, monkeypatch) -> None:
    outputs_dir = tmp_path / "outputs" / "runs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = tmp_path / "featureflow.yaml"
    _write_cfg(cfg_path, outputs_dir, tmp_path)
    monkeypatch.setenv("FEATUREFLOW_CONFIG_PATH", str(cfg_path))
    monkeypatch.setattr(cli_main, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(cli_main, "generate_run_id", lambda: "run_gate_001")

    runner = CliRunner()
    result = runner.invoke(cli_main.app, ["run", "--story", "Gate story"])

    assert result.exit_code == 0
    assert "Run created: run_gate_001" in result.output
    assert "run ff approve --run-id run_gate_001 --gate plan" in result.output

    run_data = read_run("run_gate_001", str(outputs_dir))
    assert run_data["status"] == STATUS_WAITING_APPROVAL_PLAN
    assert (outputs_dir / "run_gate_001" / "change-request.md").exists()
    assert (outputs_dir / "run_gate_001" / "test-plan.md").exists()


def test_run_requires_story_flag(tmp_path: Path, monkeypatch) -> None:
    outputs_dir = tmp_path / "outputs" / "runs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = tmp_path / "featureflow.yaml"
    _write_cfg(cfg_path, outputs_dir, tmp_path)
    monkeypatch.setenv("FEATUREFLOW_CONFIG_PATH", str(cfg_path))
    monkeypatch.setattr(cli_main, "get_project_root", lambda: tmp_path)

    runner = CliRunner()
    result = runner.invoke(cli_main.app, ["run"])

    assert result.exit_code != 0
    assert "Missing option '--story'" in result.output


def test_approve_plan_succeeds_and_persists_approval(tmp_path: Path, monkeypatch) -> None:
    outputs_dir = tmp_path / "outputs" / "runs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = tmp_path / "featureflow.yaml"
    _write_cfg(cfg_path, outputs_dir, tmp_path)
    monkeypatch.setenv("FEATUREFLOW_CONFIG_PATH", str(cfg_path))
    monkeypatch.setattr(cli_main, "get_project_root", lambda: tmp_path)

    run_id = "run_plan"
    init_run(run_id, {"story": "test"}, str(outputs_dir), [str(tmp_path)])
    _advance_status(
        run_id,
        outputs_dir,
        tmp_path,
        [STATUS_PLANNED, STATUS_WAITING_APPROVAL_PLAN],
    )

    runner = CliRunner()
    result = runner.invoke(cli_main.app, ["approve", "--run-id", run_id, "--gate", "plan"])

    assert result.exit_code == 0
    run_data = read_run(run_id, str(outputs_dir))
    assert run_data["status"] == STATUS_APPROVED_PLAN
    assert isinstance(run_data["approvals"], list)
    assert run_data["approvals"][-1]["gate"] == "plan"
    assert run_data["approvals"][-1]["approver"] == "local"
    assert run_data["approvals"][-1]["approved_at"]


def test_approve_patch_fails_outside_expected_status(tmp_path: Path, monkeypatch) -> None:
    outputs_dir = tmp_path / "outputs" / "runs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = tmp_path / "featureflow.yaml"
    _write_cfg(cfg_path, outputs_dir, tmp_path)
    monkeypatch.setenv("FEATUREFLOW_CONFIG_PATH", str(cfg_path))
    monkeypatch.setattr(cli_main, "get_project_root", lambda: tmp_path)

    run_id = "run_wrong_patch"
    init_run(run_id, {"story": "test"}, str(outputs_dir), [str(tmp_path)])
    _advance_status(
        run_id,
        outputs_dir,
        tmp_path,
        [STATUS_PLANNED, STATUS_WAITING_APPROVAL_PLAN],
    )

    runner = CliRunner()
    result = runner.invoke(cli_main.app, ["approve", "--run-id", run_id, "--gate", "patch"])

    assert result.exit_code == 1
    assert "Expected status 'WAITING_APPROVAL_PATCH'" in result.output


def test_approve_patch_succeeds_and_persists_approval(tmp_path: Path, monkeypatch) -> None:
    outputs_dir = tmp_path / "outputs" / "runs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = tmp_path / "featureflow.yaml"
    _write_cfg(cfg_path, outputs_dir, tmp_path)
    monkeypatch.setenv("FEATUREFLOW_CONFIG_PATH", str(cfg_path))
    monkeypatch.setattr(cli_main, "get_project_root", lambda: tmp_path)

    run_id = "run_patch"
    init_run(run_id, {"story": "test"}, str(outputs_dir), [str(tmp_path)])
    _advance_status(
        run_id,
        outputs_dir,
        tmp_path,
        [
            STATUS_PLANNED,
            STATUS_WAITING_APPROVAL_PLAN,
            STATUS_APPROVED_PLAN,
            STATUS_PATCH_PROPOSED,
            STATUS_WAITING_APPROVAL_PATCH,
        ],
    )

    runner = CliRunner()
    result = runner.invoke(cli_main.app, ["approve", "--run-id", run_id, "--gate", "patch"])

    assert result.exit_code == 0
    run_data = read_run(run_id, str(outputs_dir))
    assert run_data["status"] == "APPROVED_PATCH"
    assert isinstance(run_data["approvals"], list)
    assert run_data["approvals"][-1]["gate"] == "patch"
    assert run_data["approvals"][-1]["approver"] == "local"
    assert run_data["approvals"][-1]["approved_at"]


def test_approve_rejects_invalid_gate_value(tmp_path: Path, monkeypatch) -> None:
    outputs_dir = tmp_path / "outputs" / "runs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = tmp_path / "featureflow.yaml"
    _write_cfg(cfg_path, outputs_dir, tmp_path)
    monkeypatch.setenv("FEATUREFLOW_CONFIG_PATH", str(cfg_path))
    monkeypatch.setattr(cli_main, "get_project_root", lambda: tmp_path)

    run_id = "run_bad_gate"
    init_run(run_id, {"story": "test"}, str(outputs_dir), [str(tmp_path)])
    _advance_status(
        run_id,
        outputs_dir,
        tmp_path,
        [STATUS_PLANNED, STATUS_WAITING_APPROVAL_PLAN],
    )

    runner = CliRunner()
    result = runner.invoke(cli_main.app, ["approve", "--run-id", run_id, "--gate", "nope"])

    assert result.exit_code == 1
    assert "Invalid gate 'nope'" in result.output


def test_approve_final_transitions_to_finalized(tmp_path: Path, monkeypatch) -> None:
    outputs_dir = tmp_path / "outputs" / "runs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = tmp_path / "featureflow.yaml"
    _write_cfg(cfg_path, outputs_dir, tmp_path)
    monkeypatch.setenv("FEATUREFLOW_CONFIG_PATH", str(cfg_path))
    monkeypatch.setattr(cli_main, "get_project_root", lambda: tmp_path)

    run_id = "run_final"
    init_run(run_id, {"story": "test"}, str(outputs_dir), [str(tmp_path)])
    _advance_status(
        run_id,
        outputs_dir,
        tmp_path,
        [
            STATUS_PLANNED,
            STATUS_WAITING_APPROVAL_PLAN,
            STATUS_APPROVED_PLAN,
            STATUS_PATCH_PROPOSED,
            STATUS_WAITING_APPROVAL_PATCH,
            STATUS_APPROVED_PATCH,
            STATUS_TESTS_RUNNING,
            STATUS_TESTS_PASSED,
            STATUS_WAITING_APPROVAL_FINAL,
        ],
    )

    runner = CliRunner()
    result = runner.invoke(cli_main.app, ["approve", "--run-id", run_id, "--gate", "final"])

    assert result.exit_code == 0
    run_data = read_run(run_id, str(outputs_dir))
    assert run_data["status"] == STATUS_FINALIZED
    assert run_data["approvals"][-1]["gate"] == "final"


def test_next_reports_stub_actions_for_key_statuses(tmp_path: Path, monkeypatch) -> None:
    outputs_dir = tmp_path / "outputs" / "runs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = tmp_path / "featureflow.yaml"
    _write_cfg(cfg_path, outputs_dir, tmp_path)
    monkeypatch.setenv("FEATUREFLOW_CONFIG_PATH", str(cfg_path))
    monkeypatch.setattr(cli_main, "get_project_root", lambda: tmp_path)
    runner = CliRunner()

    cases = [
        ("run_next_plan", [STATUS_PLANNED, STATUS_WAITING_APPROVAL_PLAN], "--gate plan"),
        (
            "run_next_patch",
            [
                STATUS_PLANNED,
                STATUS_WAITING_APPROVAL_PLAN,
                STATUS_APPROVED_PLAN,
                STATUS_PATCH_PROPOSED,
                STATUS_WAITING_APPROVAL_PATCH,
            ],
            "--gate patch",
        ),
        (
            "run_next_final",
            [
                STATUS_PLANNED,
                STATUS_WAITING_APPROVAL_PLAN,
                STATUS_APPROVED_PLAN,
                STATUS_PATCH_PROPOSED,
                STATUS_WAITING_APPROVAL_PATCH,
                STATUS_APPROVED_PATCH,
                STATUS_TESTS_RUNNING,
                STATUS_TESTS_PASSED,
                STATUS_WAITING_APPROVAL_FINAL,
            ],
            "--gate final",
        ),
    ]

    for run_id, statuses, expected in cases:
        init_run(run_id, {"story": "test"}, str(outputs_dir), [str(tmp_path)])
        _advance_status(run_id, outputs_dir, tmp_path, statuses)
        result = runner.invoke(cli_main.app, ["next", "--run-id", run_id])
        assert result.exit_code == 0
        assert expected in result.output

        run_data = read_run(run_id, str(outputs_dir))
        assert run_data["status"] in {
            STATUS_WAITING_APPROVAL_PLAN,
            STATUS_WAITING_APPROVAL_PATCH,
            STATUS_WAITING_APPROVAL_FINAL,
        }


def test_next_reports_already_finalized(tmp_path: Path, monkeypatch) -> None:
    outputs_dir = tmp_path / "outputs" / "runs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = tmp_path / "featureflow.yaml"
    _write_cfg(cfg_path, outputs_dir, tmp_path)
    monkeypatch.setenv("FEATUREFLOW_CONFIG_PATH", str(cfg_path))
    monkeypatch.setattr(cli_main, "get_project_root", lambda: tmp_path)

    run_id = "run_next_done"
    init_run(run_id, {"story": "test"}, str(outputs_dir), [str(tmp_path)])
    _advance_status(
        run_id,
        outputs_dir,
        tmp_path,
        [
            STATUS_PLANNED,
            STATUS_WAITING_APPROVAL_PLAN,
            STATUS_APPROVED_PLAN,
            STATUS_PATCH_PROPOSED,
            STATUS_WAITING_APPROVAL_PATCH,
            STATUS_APPROVED_PATCH,
            STATUS_TESTS_RUNNING,
            STATUS_TESTS_PASSED,
            STATUS_WAITING_APPROVAL_FINAL,
            STATUS_FINALIZED,
        ],
    )

    runner = CliRunner()
    result = runner.invoke(cli_main.app, ["next", "--run-id", run_id])
    assert result.exit_code == 0
    assert "already finalized" in result.output


def test_next_transitions_approved_plan_to_patch_proposed(tmp_path: Path, monkeypatch) -> None:
    outputs_dir = tmp_path / "outputs" / "runs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = tmp_path / "featureflow.yaml"
    _write_cfg(cfg_path, outputs_dir, tmp_path)
    monkeypatch.setenv("FEATUREFLOW_CONFIG_PATH", str(cfg_path))
    monkeypatch.setattr(cli_main, "get_project_root", lambda: tmp_path)

    run_id = "run_next_approved_plan"
    init_run(run_id, {"story": "test"}, str(outputs_dir), [str(tmp_path)])
    _advance_status(
        run_id,
        outputs_dir,
        tmp_path,
        [STATUS_PLANNED, STATUS_WAITING_APPROVAL_PLAN, STATUS_APPROVED_PLAN],
    )

    runner = CliRunner()
    result = runner.invoke(cli_main.app, ["next", "--run-id", run_id])
    assert result.exit_code == 0
    run_data = read_run(run_id, str(outputs_dir))
    assert run_data["status"] == STATUS_PATCH_PROPOSED


def test_next_transitions_patch_proposed_to_waiting_patch(tmp_path: Path, monkeypatch) -> None:
    outputs_dir = tmp_path / "outputs" / "runs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = tmp_path / "featureflow.yaml"
    _write_cfg(cfg_path, outputs_dir, tmp_path)
    monkeypatch.setenv("FEATUREFLOW_CONFIG_PATH", str(cfg_path))
    monkeypatch.setattr(cli_main, "get_project_root", lambda: tmp_path)

    run_id = "run_next_patch_proposed"
    init_run(run_id, {"story": "test"}, str(outputs_dir), [str(tmp_path)])
    _advance_status(
        run_id,
        outputs_dir,
        tmp_path,
        [STATUS_PLANNED, STATUS_WAITING_APPROVAL_PLAN, STATUS_APPROVED_PLAN, STATUS_PATCH_PROPOSED],
    )

    runner = CliRunner()
    result = runner.invoke(cli_main.app, ["next", "--run-id", run_id])
    assert result.exit_code == 0
    run_data = read_run(run_id, str(outputs_dir))
    assert run_data["status"] == STATUS_WAITING_APPROVAL_PATCH


def test_next_runs_tests_for_approved_patch(tmp_path: Path, monkeypatch) -> None:
    outputs_dir = tmp_path / "outputs" / "runs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = tmp_path / "featureflow.yaml"
    _write_cfg(cfg_path, outputs_dir, tmp_path)
    monkeypatch.setenv("FEATUREFLOW_CONFIG_PATH", str(cfg_path))
    monkeypatch.setattr(cli_main, "get_project_root", lambda: tmp_path)

    def _fake_run_command(*_args, **_kwargs):
        return {"exit_code": 0, "stdout": "ok", "stderr": ""}

    monkeypatch.setattr(cli_main, "run_command", _fake_run_command)

    run_id = "run_next_approved_patch"
    init_run(run_id, {"story": "test"}, str(outputs_dir), [str(tmp_path)])
    create_run_artifacts(run_id, str(outputs_dir), [str(tmp_path)])
    _advance_status(
        run_id,
        outputs_dir,
        tmp_path,
        [
            STATUS_PLANNED,
            STATUS_WAITING_APPROVAL_PLAN,
            STATUS_APPROVED_PLAN,
            STATUS_PATCH_PROPOSED,
            STATUS_WAITING_APPROVAL_PATCH,
            STATUS_APPROVED_PATCH,
        ],
    )

    runner = CliRunner()
    result = runner.invoke(cli_main.app, ["next", "--run-id", run_id])
    assert result.exit_code == 0
    run_data = read_run(run_id, str(outputs_dir))
    assert run_data["status"] == STATUS_TESTS_PASSED
    assert run_data["test_results"]["exit_code"] == 0


def test_next_loops_on_tests_failed(tmp_path: Path, monkeypatch) -> None:
    outputs_dir = tmp_path / "outputs" / "runs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = tmp_path / "featureflow.yaml"
    _write_cfg(cfg_path, outputs_dir, tmp_path)
    monkeypatch.setenv("FEATUREFLOW_CONFIG_PATH", str(cfg_path))
    monkeypatch.setattr(cli_main, "get_project_root", lambda: tmp_path)

    run_id = "run_next_tests_failed"
    init_run(run_id, {"story": "test"}, str(outputs_dir), [str(tmp_path)])
    _advance_status(
        run_id,
        outputs_dir,
        tmp_path,
        [
            STATUS_PLANNED,
            STATUS_WAITING_APPROVAL_PLAN,
            STATUS_APPROVED_PLAN,
            STATUS_PATCH_PROPOSED,
            STATUS_WAITING_APPROVAL_PATCH,
            STATUS_APPROVED_PATCH,
            STATUS_TESTS_RUNNING,
            STATUS_TESTS_FAILED,
        ],
    )

    runner = CliRunner()
    result = runner.invoke(cli_main.app, ["next", "--run-id", run_id])
    assert result.exit_code == 0
    run_data = read_run(run_id, str(outputs_dir))
    assert run_data["status"] == STATUS_PATCH_PROPOSED
    assert run_data["loop_iters"] == 1


def test_next_marks_failed_when_max_iters_exceeded(tmp_path: Path, monkeypatch) -> None:
    outputs_dir = tmp_path / "outputs" / "runs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = tmp_path / "featureflow.yaml"
    _write_cfg(cfg_path, outputs_dir, tmp_path)
    monkeypatch.setenv("FEATUREFLOW_CONFIG_PATH", str(cfg_path))
    monkeypatch.setattr(cli_main, "get_project_root", lambda: tmp_path)

    run_id = "run_next_max_iters"
    init_run(run_id, {"story": "test"}, str(outputs_dir), [str(tmp_path)])
    _advance_status(
        run_id,
        outputs_dir,
        tmp_path,
        [
            STATUS_PLANNED,
            STATUS_WAITING_APPROVAL_PLAN,
            STATUS_APPROVED_PLAN,
            STATUS_PATCH_PROPOSED,
            STATUS_WAITING_APPROVAL_PATCH,
            STATUS_APPROVED_PATCH,
            STATUS_TESTS_RUNNING,
            STATUS_TESTS_FAILED,
        ],
    )

    data = read_run(run_id, str(outputs_dir))
    data["loop_iters"] = 1
    write_run(run_id, str(outputs_dir), data, [str(tmp_path)])

    runner = CliRunner()
    result = runner.invoke(cli_main.app, ["next", "--run-id", run_id])
    assert result.exit_code == 0
    run_data = read_run(run_id, str(outputs_dir))
    assert run_data["status"] == "FAILED"
    assert run_data["failure_reason"] == "Max iterations exceeded"
