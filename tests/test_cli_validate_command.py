from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from cli.main import app


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


def test_validate_command_returns_invalid_for_missing_contract(
    tmp_path: Path, monkeypatch
) -> None:
    outputs_dir = tmp_path / "outputs" / "runs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = tmp_path / "featureflow.yaml"
    _write_cfg(cfg_path, outputs_dir, tmp_path)
    monkeypatch.setenv("FEATUREFLOW_CONFIG_PATH", str(cfg_path))

    runner = CliRunner()
    result = runner.invoke(app, ["validate", "--run-id", "run_missing"])

    assert result.exit_code == 1
    assert "INVALID" in result.output
    assert "File not found" in result.output


def test_validate_command_returns_valid_for_complete_contract(
    tmp_path: Path, monkeypatch
) -> None:
    outputs_dir = tmp_path / "outputs" / "runs"
    run_dir = outputs_dir / "run_ok"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "change-request.md").write_text(
        """Objective: Validate contract command
Scope: Add contract checks
Out of scope: No web changes
Definition of done: Command reports contract as valid
Risks: False positives in parser
""",
        encoding="utf-8",
    )
    cfg_path = tmp_path / "featureflow.yaml"
    _write_cfg(cfg_path, outputs_dir, tmp_path)
    monkeypatch.setenv("FEATUREFLOW_CONFIG_PATH", str(cfg_path))

    runner = CliRunner()
    result = runner.invoke(app, ["validate", "--run-id", "run_ok"])

    assert result.exit_code == 0
    assert "VALID" in result.output
