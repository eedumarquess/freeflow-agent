from __future__ import annotations

from pathlib import Path

from featureflow.artifacts import create_run_artifacts
from featureflow.storage import STATUS_APPROVED_PATCH, STATUS_TESTS_RUNNING, init_run, read_run
from featureflow.workflow.nodes import NodeContext, apply_changes_node


def _write_cfg(path: Path, outputs_dir: Path, allowed_root: Path) -> dict:
    cfg = {
        "project": {"base_branch": "main"},
        "runs": {"outputs_dir": outputs_dir.as_posix(), "max_iters": 2, "timeout_seconds": 60},
        "security": {
            "allowed_commands": [],
            "allowed_write_roots": [allowed_root.as_posix()],
            "fs_ops": {"max_file_bytes": 524288, "max_diff_lines": 3, "max_files_changed": 5},
        },
    }
    path.write_text(
        f'''project:\n  base_branch: "main"\nruns:\n  outputs_dir: "{outputs_dir.as_posix()}"\n  max_iters: 2\n  timeout_seconds: 60\nsecurity:\n  allowed_commands: []\n  allowed_write_roots:\n    - "{allowed_root.as_posix()}"\n  fs_ops:\n    max_file_bytes: 524288\n    max_diff_lines: 3\n    max_files_changed: 5\n''',
        encoding="utf-8",
    )
    return cfg


def test_apply_changes_warns_when_small_diff_limits_are_exceeded(tmp_path: Path, monkeypatch) -> None:
    outputs_dir = tmp_path / "outputs" / "runs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = tmp_path / "featureflow.yaml"
    cfg = _write_cfg(cfg_path, outputs_dir, tmp_path)

    monkeypatch.setenv("FEATUREFLOW_CONFIG_PATH", str(cfg_path))

    import featureflow.fs_ops as fs_ops
    import featureflow.workflow.nodes as wf_nodes

    monkeypatch.setattr(fs_ops, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(wf_nodes, "ensure_agent_branch", lambda _run_id, _repo_root: "agent/run_warn")

    run_id = "run_warn"
    init_run(run_id, {"story": "warn test"}, str(outputs_dir), [str(tmp_path)])
    create_run_artifacts(run_id, str(outputs_dir), [str(tmp_path)])

    target = tmp_path / "sample.txt"
    target.write_text("old\n", encoding="utf-8")

    patch_text = """--- a/sample.txt
+++ b/sample.txt
@@ -1 +1 @@
-old
+new
"""

    run_data = read_run(run_id, str(outputs_dir))
    run_data["status"] = STATUS_APPROVED_PATCH
    run_data["edits"] = {"patch_text": patch_text, "applied_files": []}

    ctx = NodeContext(cfg=cfg, repo_root=tmp_path, outputs_dir=str(outputs_dir), allowed_roots=[str(tmp_path)])
    out = apply_changes_node(run_data, ctx)

    assert out["status"] == STATUS_TESTS_RUNNING
    assert target.read_text(encoding="utf-8") == "new\n"

    latest = read_run(run_id, str(outputs_dir))
    warnings = latest.get("scope_warnings")
    assert isinstance(warnings, list)
    assert len(warnings) == 1
    assert warnings[0]["source"] == "APPLY_CHANGES"
    assert warnings[0]["kind"] == "small_diff_limit"
    assert warnings[0]["details"]["violations"]

    report = (outputs_dir / run_id / "run-report.md").read_text(encoding="utf-8")
    assert "Scope Warning (APPLY_CHANGES)" in report
    assert "Violation `max_diff_lines`" in report
