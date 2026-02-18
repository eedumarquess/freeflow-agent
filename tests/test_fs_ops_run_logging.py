from __future__ import annotations

from pathlib import Path

import pytest

from featureflow.fs_ops import configure_run_logging, write_file
from featureflow.storage import init_run, read_run


def _write_cfg(path: Path, allowed_root: Path) -> None:
    cfg = f"""
project:
  base_branch: "main"
runs:
  outputs_dir: "outputs/runs"
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


def test_write_logs_to_run_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    cfg_path = tmp_path / "featureflow.yaml"
    _write_cfg(cfg_path, allowed)
    monkeypatch.setenv("FEATUREFLOW_CONFIG_PATH", str(cfg_path))

    run_id = "test_run"
    outputs_dir = tmp_path / "outputs" / "runs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    run_allowed_roots = [str(tmp_path)]
    init_run(run_id, {"story": "test"}, str(outputs_dir), run_allowed_roots)
    configure_run_logging(run_id, str(outputs_dir), allowed_write_roots=run_allowed_roots)

    write_file(allowed / "x.txt", "ok")

    data = read_run(run_id, str(outputs_dir))
    events = data.get("fs_ops_events")
    assert isinstance(events, list)
    assert len(events) == 1
    ev = events[0]
    assert ev["op"] == "write"
    assert ev["ok"] is True
    assert ev["bytes_written"] == 2
    assert "started_at" in ev
    assert "finished_at" in ev

