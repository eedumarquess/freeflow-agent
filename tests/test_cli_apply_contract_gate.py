from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

import cli.main as cli_main
import featureflow.fs_ops as fs_ops
from featureflow.storage import init_run, read_run


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
  fs_ops:
    max_file_bytes: 524288
    max_diff_lines: 800
    max_files_changed: 20
""".lstrip()
    path.write_text(cfg, encoding="utf-8")


def test_apply_fails_with_failed_contract_status(tmp_path: Path, monkeypatch) -> None:
    outputs_dir = tmp_path / "outputs" / "runs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = tmp_path / "featureflow.yaml"
    _write_cfg(cfg_path, outputs_dir, tmp_path)
    monkeypatch.setenv("FEATUREFLOW_CONFIG_PATH", str(cfg_path))
    monkeypatch.setattr(cli_main, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(fs_ops, "get_project_root", lambda: tmp_path)

    run_id = "run_fail"
    init_run(run_id, {"story": "test"}, str(outputs_dir), [str(tmp_path)])

    target = tmp_path / "sample.txt"
    target.write_text("old\n", encoding="utf-8")
    patch_file = tmp_path / "change.diff"
    patch_file.write_text(
        """--- a/sample.txt
+++ b/sample.txt
@@ -1 +1 @@
-old
+new
""",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(cli_main.app, ["apply", run_id, str(patch_file)])

    assert result.exit_code == 1
    assert "INVALID CONTRACT" in result.output
    run_data = read_run(run_id, str(outputs_dir))
    assert run_data["status"] == "FAILED"
    assert run_data["failure_reason"] == "Invalid change-request.md contract"
    assert isinstance(run_data["contract_issues"], list)
    assert target.read_text(encoding="utf-8") == "old\n"


def test_apply_succeeds_with_valid_contract(tmp_path: Path, monkeypatch) -> None:
    outputs_dir = tmp_path / "outputs" / "runs"
    run_dir = outputs_dir / "run_ok"
    run_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = tmp_path / "featureflow.yaml"
    _write_cfg(cfg_path, outputs_dir, tmp_path)
    monkeypatch.setenv("FEATUREFLOW_CONFIG_PATH", str(cfg_path))
    monkeypatch.setattr(cli_main, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(fs_ops, "get_project_root", lambda: tmp_path)

    run_id = "run_ok"
    init_run(run_id, {"story": "test"}, str(outputs_dir), [str(tmp_path)])
    (run_dir / "change-request.md").write_text(
        """Objective: Apply patch safely
Scope: Validate contract before apply
Out-of-scope: No API changes
Done criteria: Patch applies and run status updates
Risks: Parser rejects valid headings
""",
        encoding="utf-8",
    )

    target = tmp_path / "sample.txt"
    target.write_text("old\n", encoding="utf-8")
    patch_file = tmp_path / "change.diff"
    patch_file.write_text(
        """--- a/sample.txt
+++ b/sample.txt
@@ -1 +1 @@
-old
+new
""",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(cli_main.app, ["apply", run_id, str(patch_file)])

    assert result.exit_code == 0
    assert "Applied patch with 1 file(s) changed" in result.output
    run_data = read_run(run_id, str(outputs_dir))
    assert run_data["status"] == "PATCH_PROPOSED"
    assert run_data["applied_files"] == ["sample.txt"]
    assert target.read_text(encoding="utf-8") == "new\n"
