from __future__ import annotations

from pathlib import Path

from featureflow.artifacts import create_run_artifacts
from featureflow.storage import init_run, read_run
from featureflow.workflow.nodes import NodeContext, load_context_node


def _cfg(outputs_dir: Path, allowed_root: Path) -> dict:
    return {
        "project": {"base_branch": "main"},
        "runs": {"outputs_dir": outputs_dir.as_posix(), "max_iters": 2, "timeout_seconds": 60},
        "security": {
            "allowed_commands": [["python", "-m", "pytest", "-q"]],
            "allowed_write_roots": [allowed_root.as_posix()],
            "fs_ops": {"max_file_bytes": 524288, "max_diff_lines": 800, "max_files_changed": 20},
        },
        "llm": {
            "enabled": True,
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "api_key": "test-key",
            "max_repo_tree_entries": 100,
            "max_repo_files_index_entries": 1000,
        },
    }


def test_load_context_node_builds_extended_context_pack(tmp_path: Path) -> None:
    outputs_dir = tmp_path / "outputs" / "runs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "AGENTS.md").write_text("# Agent rules", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Readme", encoding="utf-8")
    (tmp_path / "tests").mkdir(exist_ok=True)
    (tmp_path / "tests" / "test_sample.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")

    cfg = _cfg(outputs_dir, tmp_path)
    run_id = "run_context_pack"
    init_run(run_id, {"story": "Need a context pack"}, str(outputs_dir), [str(tmp_path)])
    create_run_artifacts(run_id, str(outputs_dir), [str(tmp_path)])
    ctx = NodeContext(cfg=cfg, repo_root=tmp_path, outputs_dir=str(outputs_dir), allowed_roots=[str(tmp_path)])

    data = read_run(run_id, str(outputs_dir))
    out = load_context_node(data, ctx)
    context = out["context"]

    assert "repo_tree" in context
    assert "repo_files_index" in context
    assert "tests_summary" in context
    assert "highlight_dirs" in context
    assert "AGENTS.md" in context["key_files"]
    assert "README.md" in context["key_files"]
    assert any(path == "tests/test_sample.py" for path in context["repo_files_index"])
    assert "pytest" in context["tests_summary"].lower()
