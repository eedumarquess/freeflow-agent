from __future__ import annotations

from pathlib import Path

import featureflow.workflow.nodes as wf_nodes
from featureflow.artifacts import create_run_artifacts
from featureflow.llm.models import PlannerOutput, ProposedStepOutput, ProposerOutput
from featureflow.storage import STATUS_PATCH_PROPOSED, init_run, read_run
from featureflow.workflow.nodes import NodeContext, load_context_node, plan_node, propose_changes_node


def _cfg(outputs_dir: Path, allowed_root: Path) -> dict:
    return {
        "project": {"base_branch": "main"},
        "runs": {"outputs_dir": outputs_dir.as_posix(), "max_iters": 2, "timeout_seconds": 60},
        "security": {
            "allowed_commands": [],
            "allowed_write_roots": [allowed_root.as_posix()],
            "fs_ops": {"max_file_bytes": 524288, "max_diff_lines": 800, "max_files_changed": 20},
        },
        "llm": {
            "enabled": True,
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "api_key": "test-key",
            "timeout_seconds": 30,
            "temperature": 0,
            "max_repo_tree_entries": 50,
            "max_diff_chars": 2000,
            "max_key_file_chars": 2000,
        },
    }


def test_plan_node_uses_llm_when_enabled(tmp_path: Path, monkeypatch) -> None:
    outputs_dir = tmp_path / "outputs" / "runs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    cfg = _cfg(outputs_dir, tmp_path)
    run_id = "run_plan_llm"
    init_run(run_id, {"story": "Implement feature"}, str(outputs_dir), [str(tmp_path)])
    create_run_artifacts(run_id, str(outputs_dir), [str(tmp_path)])
    ctx = NodeContext(cfg=cfg, repo_root=tmp_path, outputs_dir=str(outputs_dir), allowed_roots=[str(tmp_path)])

    monkeypatch.setattr(
        wf_nodes,
        "generate_plan",
        lambda **_kwargs: PlannerOutput(
            change_request_md="# Change Request\n\n## Objective\n- Implement feature",
            test_plan_md="# Test Plan\n\n## Manual Validation\n- Validate flow",
        ),
    )

    data = read_run(run_id, str(outputs_dir))
    out = plan_node(data, ctx)
    assert "Implement feature" in out["plan"]["change_request_md"]
    assert "Test Plan" in out["plan"]["test_plan_md"]

    run_report = (outputs_dir / run_id / "run-report.md").read_text(encoding="utf-8")
    assert "Source: `llm`" in run_report


def test_plan_node_falls_back_when_llm_fails(tmp_path: Path, monkeypatch) -> None:
    outputs_dir = tmp_path / "outputs" / "runs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    cfg = _cfg(outputs_dir, tmp_path)
    run_id = "run_plan_fallback"
    init_run(run_id, {"story": "Implement feature"}, str(outputs_dir), [str(tmp_path)])
    create_run_artifacts(run_id, str(outputs_dir), [str(tmp_path)])
    ctx = NodeContext(cfg=cfg, repo_root=tmp_path, outputs_dir=str(outputs_dir), allowed_roots=[str(tmp_path)])

    monkeypatch.setattr(wf_nodes, "generate_plan", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    data = read_run(run_id, str(outputs_dir))
    out = plan_node(data, ctx)
    assert "# Change Request" in out["plan"]["change_request_md"]
    assert "# Test Plan" in out["plan"]["test_plan_md"]

    run_report = (outputs_dir / run_id / "run-report.md").read_text(encoding="utf-8")
    assert "Source: `fallback`" in run_report


def test_propose_changes_falls_back_when_llm_steps_are_invalid(tmp_path: Path, monkeypatch) -> None:
    outputs_dir = tmp_path / "outputs" / "runs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    cfg = _cfg(outputs_dir, tmp_path)
    run_id = "run_propose_fallback"
    init_run(run_id, {"story": "Implement feature"}, str(outputs_dir), [str(tmp_path)])
    create_run_artifacts(run_id, str(outputs_dir), [str(tmp_path)])
    ctx = NodeContext(cfg=cfg, repo_root=tmp_path, outputs_dir=str(outputs_dir), allowed_roots=[str(tmp_path)])

    monkeypatch.setattr(
        wf_nodes,
        "generate_proposed_steps",
        lambda **_kwargs: ProposerOutput(
            steps=[
                ProposedStepOutput(id="s1", file="../escape.py", intent="bad", reason="bad"),
                ProposedStepOutput(id="s2", file="C:/absolute.py", intent="bad", reason="bad"),
            ]
        ),
    )

    data = read_run(run_id, str(outputs_dir))
    data = load_context_node(data, ctx)
    out = propose_changes_node(data, ctx)
    assert out["status"] == STATUS_PATCH_PROPOSED
    assert out["edits"]["proposed_steps"][0]["id"] == "step-1"

    run_report = (outputs_dir / run_id / "run-report.md").read_text(encoding="utf-8")
    assert "Source: `fallback-deterministic`" in run_report


def test_propose_changes_uses_llm_steps_when_valid(tmp_path: Path, monkeypatch) -> None:
    outputs_dir = tmp_path / "outputs" / "runs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    cfg = _cfg(outputs_dir, tmp_path)
    run_id = "run_propose_llm"
    init_run(run_id, {"story": "Implement feature"}, str(outputs_dir), [str(tmp_path)])
    create_run_artifacts(run_id, str(outputs_dir), [str(tmp_path)])
    ctx = NodeContext(cfg=cfg, repo_root=tmp_path, outputs_dir=str(outputs_dir), allowed_roots=[str(tmp_path)])

    monkeypatch.setattr(
        wf_nodes,
        "generate_proposed_steps",
        lambda **_kwargs: ProposerOutput(
            steps=[
                ProposedStepOutput(
                    id="s1",
                    file="featureflow\\workflow\\nodes.py",
                    intent="update-plan",
                    reason="Need to implement behavior",
                )
            ]
        ),
    )

    data = read_run(run_id, str(outputs_dir))
    data = load_context_node(data, ctx)
    out = propose_changes_node(data, ctx)
    assert out["status"] == STATUS_PATCH_PROPOSED
    assert out["edits"]["proposed_steps"][0]["id"] == "s1"
    assert out["edits"]["proposed_steps"][0]["file"] == "featureflow/workflow/nodes.py"

    run_report = (outputs_dir / run_id / "run-report.md").read_text(encoding="utf-8")
    assert "Source: `llm`" in run_report
