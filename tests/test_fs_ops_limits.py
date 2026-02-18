from __future__ import annotations

from pathlib import Path

import pytest

from featureflow.errors import DiffTooLargeError, FileTooLargeError
from featureflow.fs_ops import apply_patch, write_file


def _write_cfg(
    path: Path,
    allowed_root: Path,
    *,
    max_file_bytes: int,
    max_diff_lines: int,
    max_files_changed: int = 20,
) -> None:
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
    max_file_bytes: {max_file_bytes}
    max_diff_lines: {max_diff_lines}
    max_files_changed: {max_files_changed}
""".lstrip()
    path.write_text(cfg, encoding="utf-8")


def test_write_rejects_large_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    cfg_path = tmp_path / "featureflow.yaml"
    _write_cfg(cfg_path, allowed, max_file_bytes=10, max_diff_lines=800)
    monkeypatch.setenv("FEATUREFLOW_CONFIG_PATH", str(cfg_path))

    with pytest.raises(FileTooLargeError):
        write_file(allowed / "x.txt", "01234567890")


def test_apply_patch_rejects_large_diff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    cfg_path = tmp_path / "featureflow.yaml"
    _write_cfg(cfg_path, allowed, max_file_bytes=524288, max_diff_lines=3)
    monkeypatch.setenv("FEATUREFLOW_CONFIG_PATH", str(cfg_path))

    diff = "a\nb\nc\nd\n"
    with pytest.raises(DiffTooLargeError):
        apply_patch(allowed, diff)

