from __future__ import annotations

from pathlib import Path

import pytest

from featureflow.errors import PathNotAllowedError
from featureflow.fs_ops import write_file


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


def test_write_outside_allowed_root_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    cfg_path = tmp_path / "featureflow.yaml"
    _write_cfg(cfg_path, allowed)
    monkeypatch.setenv("FEATUREFLOW_CONFIG_PATH", str(cfg_path))

    outside = tmp_path / "outside" / "x.txt"
    with pytest.raises(PathNotAllowedError):
        write_file(outside, "nope")


def test_path_traversal_is_blocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    cfg_path = tmp_path / "featureflow.yaml"
    _write_cfg(cfg_path, allowed)
    monkeypatch.setenv("FEATUREFLOW_CONFIG_PATH", str(cfg_path))

    traversal = str(allowed / ".." / "outside" / "x.txt")
    with pytest.raises(PathNotAllowedError):
        write_file(traversal, "nope")


def test_symlink_escape_is_blocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    cfg_path = tmp_path / "featureflow.yaml"
    _write_cfg(cfg_path, allowed)
    monkeypatch.setenv("FEATUREFLOW_CONFIG_PATH", str(cfg_path))

    link = allowed / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"Symlinks not available on this system: {exc}")

    with pytest.raises(PathNotAllowedError):
        write_file(link / "evil.txt", "nope")

