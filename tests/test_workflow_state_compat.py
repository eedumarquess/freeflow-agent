from __future__ import annotations

from pathlib import Path

from featureflow.artifacts import create_run_artifacts
from featureflow.storage import init_run, read_run
from featureflow.workflow.state import build_graph_state, merge_state_into_run_data


def _write_cfg(path: Path, outputs_dir: Path, allowed_root: Path) -> dict:
    cfg = {
        "project": {"base_branch": "main"},
        "runs": {
            "outputs_dir": outputs_dir.as_posix(),
            "max_iters": 2,
            "timeout_seconds": 60,
        },
        "security": {
            "allowed_commands": [],
            "allowed_write_roots": [allowed_root.as_posix()],
            "fs_ops": {
                "max_file_bytes": 524288,
                "max_diff_lines": 800,
                "max_files_changed": 20,
            },
        },
    }
    text = (
        f'project:\n  base_branch: "main"\n'
        f'runs:\n  outputs_dir: "{outputs_dir.as_posix()}"\n  max_iters: 2\n  timeout_seconds: 60\n'
        f'security:\n  allowed_commands: []\n  allowed_write_roots:\n    - "{allowed_root.as_posix()}"\n'
        "  fs_ops:\n    max_file_bytes: 524288\n    max_diff_lines: 800\n    max_files_changed: 20\n"
    )
    path.write_text(text, encoding="utf-8")
    return cfg


def test_state_roundtrip_keeps_legacy_fields(tmp_path: Path) -> None:
    outputs_dir = tmp_path / "outputs" / "runs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    cfg = _write_cfg(tmp_path / "featureflow.yaml", outputs_dir, tmp_path)

    run_id = "run_state_compat"
    init_run(run_id, {"story": "state test"}, str(outputs_dir), [str(tmp_path)])
    create_run_artifacts(run_id, str(outputs_dir), [str(tmp_path)])
    run_data = read_run(run_id, str(outputs_dir))

    state = build_graph_state(run_data, cfg, tmp_path, str(outputs_dir))
    state.status = "WAITING_APPROVAL_PLAN"
    state.loop_iters = 1
    state.edits.applied_files = ["featureflow/workflow/state.py"]
    state.tests.results = [{"exit_code": 0, "stdout": "ok", "stderr": ""}]
    merged = merge_state_into_run_data(state, run_data)

    assert merged["status"] == "WAITING_APPROVAL_PLAN"
    assert merged["loop_iters"] == 1
    assert merged["test_results"]["exit_code"] == 0
    assert merged["approvals"] == []
    assert "plan" in merged
    assert "context" in merged
    assert "edits" in merged
    assert "tests" in merged
    assert "risk" in merged
    assert "limits" in merged
    assert "status_meta" in merged
