from __future__ import annotations

from pathlib import Path

from featureflow.artifacts import create_run_artifacts
from featureflow.storage import STATUS_PATCH_PROPOSED, STATUS_WAITING_APPROVAL_PATCH, init_run, read_run
from featureflow.workflow.nodes import NodeContext, await_approval_node, load_context_node, plan_node, propose_changes_node


def _cfg(outputs_dir: Path, allowed_root: Path) -> dict:
    return {
        "project": {"base_branch": "main"},
        "runs": {"outputs_dir": outputs_dir.as_posix(), "max_iters": 2, "timeout_seconds": 60},
        "security": {
            "allowed_commands": [],
            "allowed_write_roots": [allowed_root.as_posix()],
            "fs_ops": {"max_file_bytes": 524288, "max_diff_lines": 800, "max_files_changed": 20},
        },
    }


def test_nodes_load_plan_propose_and_pause(tmp_path: Path) -> None:
    outputs_dir = tmp_path / "outputs" / "runs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    cfg = _cfg(outputs_dir, tmp_path)

    run_id = "run_nodes_mvp"
    init_run(run_id, {"story": "Implement MVP"}, str(outputs_dir), [str(tmp_path)])
    create_run_artifacts(run_id, str(outputs_dir), [str(tmp_path)])
    ctx = NodeContext(cfg=cfg, repo_root=tmp_path, outputs_dir=str(outputs_dir), allowed_roots=[str(tmp_path)])

    data = read_run(run_id, str(outputs_dir))
    data = load_context_node(data, ctx)
    data = plan_node(data, ctx)
    data = propose_changes_node(data, ctx)
    assert data["status"] == STATUS_PATCH_PROPOSED
    assert data["edits"]["proposed_steps"]

    data = await_approval_node(data, ctx)
    assert data["status"] == STATUS_WAITING_APPROVAL_PATCH
    assert data["approvals"]["pending_gate"] == "patch"
