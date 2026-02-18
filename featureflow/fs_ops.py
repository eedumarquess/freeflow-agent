from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .config import get_allowed_write_roots, get_project_root, load_config
from .errors import DiffTooLargeError, FileTooLargeError, PatchApplyError, PathNotAllowedError
from .storage import read_run, write_run
from .time_utils import utc_now_iso
from .unified_diff import apply_hunks, parse_unified_diff, relpath_and_kind


DEFAULT_MAX_FILE_BYTES = 512 * 1024
DEFAULT_MAX_DIFF_LINES = 800
DEFAULT_MAX_FILES_CHANGED = 20


_RUN_LOGGING: dict[str, Any] | None = None


def configure_run_logging(
    run_id: str,
    outputs_dir: str,
    allowed_write_roots: list[str] | None = None,
) -> None:
    global _RUN_LOGGING
    _RUN_LOGGING = {
        "run_id": run_id,
        "outputs_dir": outputs_dir,
        "allowed_write_roots": allowed_write_roots,
    }


def _append_run_event(event: dict) -> None:
    if _RUN_LOGGING is None:
        return
    run_id = _RUN_LOGGING["run_id"]
    outputs_dir = _RUN_LOGGING["outputs_dir"]
    allowed_roots = _RUN_LOGGING.get("allowed_write_roots")

    data = read_run(run_id, outputs_dir)
    events = data.get("fs_ops_events")
    if not isinstance(events, list):
        events = []
    events.append(event)
    data["fs_ops_events"] = events
    write_run(run_id, outputs_dir, data, allowed_roots)


def _load_cfg() -> dict:
    override = os.environ.get("FEATUREFLOW_CONFIG_PATH")
    return load_config(override)


def _limits_from_cfg(cfg: dict) -> tuple[int, int, int]:
    security = cfg.get("security", {}) if isinstance(cfg, dict) else {}
    fs_cfg = security.get("fs_ops", {}) if isinstance(security, dict) else {}
    if not isinstance(fs_cfg, dict):
        fs_cfg = {}
    max_file_bytes = int(fs_cfg.get("max_file_bytes", DEFAULT_MAX_FILE_BYTES))
    max_diff_lines = int(fs_cfg.get("max_diff_lines", DEFAULT_MAX_DIFF_LINES))
    max_files_changed = int(fs_cfg.get("max_files_changed", DEFAULT_MAX_FILES_CHANGED))
    return max_file_bytes, max_diff_lines, max_files_changed


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _reject_traversal(raw: str) -> None:
    if "\x00" in raw:
        raise PathNotAllowedError("Path contains NUL byte")
    normalized = raw.replace("\\", "/")
    parts = [p for p in normalized.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise PathNotAllowedError(f"Path traversal not allowed: {raw!r}")


def _validate_allowed_path(abs_path: Path, allowed_roots: list[str], repo_root: Path) -> None:
    abs_path = abs_path.resolve(strict=False)
    for root in allowed_roots:
        root_path = Path(root)
        if not root_path.is_absolute():
            root_path = repo_root / root_path
        root_path = root_path.resolve(strict=False)
        if abs_path == root_path or _is_relative_to(abs_path, root_path):
            return
    raise PathNotAllowedError(f"Path not allowed: {abs_path}")


def _resolve_and_validate_path(path: str | Path, allowed_roots: list[str], repo_root: Path) -> Path:
    raw = str(path)
    _reject_traversal(raw)
    abs_path = Path(raw)
    if not abs_path.is_absolute():
        abs_path = (repo_root / abs_path).resolve(strict=False)
    else:
        abs_path = abs_path.resolve(strict=False)
    _validate_allowed_path(abs_path, allowed_roots, repo_root)
    return abs_path


def read_file(path: str | Path) -> str:
    started_at = utc_now_iso()
    cfg = _load_cfg()
    repo_root = get_project_root()
    allowed_roots = get_allowed_write_roots(cfg)
    max_file_bytes, _, _ = _limits_from_cfg(cfg)

    try:
        abs_path = _resolve_and_validate_path(path, allowed_roots, repo_root)
        if not abs_path.exists():
            raise FileNotFoundError(str(abs_path))
        size = abs_path.stat().st_size
        if size > max_file_bytes:
            raise FileTooLargeError(f"File too large to read: {abs_path} ({size} bytes)")
        content = abs_path.read_text(encoding="utf-8")
        _append_run_event(
            {
                "op": "read",
                "path": str(abs_path),
                "bytes_read": size,
                "started_at": started_at,
                "finished_at": utc_now_iso(),
                "ok": True,
            }
        )
        return content
    except Exception as exc:
        _append_run_event(
            {
                "op": "read",
                "path": str(path),
                "started_at": started_at,
                "finished_at": utc_now_iso(),
                "ok": False,
                "error": {"type": type(exc).__name__, "message": str(exc)},
            }
        )
        raise


def write_file(path: str | Path, content: str) -> None:
    started_at = utc_now_iso()
    cfg = _load_cfg()
    repo_root = get_project_root()
    allowed_roots = get_allowed_write_roots(cfg)
    max_file_bytes, _, _ = _limits_from_cfg(cfg)

    try:
        data = content.encode("utf-8")
        if len(data) > max_file_bytes:
            raise FileTooLargeError(f"Content too large to write: {len(data)} bytes")
        abs_path = _resolve_and_validate_path(path, allowed_roots, repo_root)
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(content, encoding="utf-8")
        _append_run_event(
            {
                "op": "write",
                "path": str(abs_path),
                "bytes_written": len(data),
                "started_at": started_at,
                "finished_at": utc_now_iso(),
                "ok": True,
            }
        )
    except Exception as exc:
        _append_run_event(
            {
                "op": "write",
                "path": str(path),
                "started_at": started_at,
                "finished_at": utc_now_iso(),
                "ok": False,
                "error": {"type": type(exc).__name__, "message": str(exc)},
            }
        )
        raise


def apply_patch(root_dir: str | Path, unified_diff_text: str) -> list[str]:
    started_at = utc_now_iso()
    cfg = _load_cfg()
    repo_root = get_project_root()
    allowed_roots = get_allowed_write_roots(cfg)
    max_file_bytes, max_diff_lines, max_files_changed = _limits_from_cfg(cfg)

    try:
        if len(unified_diff_text.splitlines()) > max_diff_lines:
            raise DiffTooLargeError(f"Diff too large: exceeds {max_diff_lines} lines")

        patches = parse_unified_diff(unified_diff_text)
        if len(patches) > max_files_changed:
            raise DiffTooLargeError(f"Too many files changed: exceeds {max_files_changed}")

        root_abs = Path(root_dir).resolve(strict=False)
        changed: list[str] = []
        bytes_written_total = 0

        for fp in patches:
            rel, kind = relpath_and_kind(fp)
            _reject_traversal(rel)
            rel_path = Path(rel)
            if rel_path.is_absolute():
                raise PatchApplyError(f"Absolute paths not allowed in patch: {rel}")
            target_abs = (root_abs / rel_path).resolve(strict=False)
            _validate_allowed_path(target_abs, allowed_roots, repo_root)

            if kind == "add":
                if target_abs.exists():
                    raise PatchApplyError(f"File already exists (add): {target_abs}")
                original = ""
            else:
                if not target_abs.exists():
                    raise PatchApplyError(f"File does not exist ({kind}): {target_abs}")
                size = target_abs.stat().st_size
                if size > max_file_bytes:
                    raise FileTooLargeError(f"File too large to patch: {target_abs} ({size} bytes)")
                original = target_abs.read_text(encoding="utf-8")

            if kind == "delete":
                if fp.hunks:
                    apply_hunks(original, fp.hunks)
                target_abs.unlink()
            else:
                new_content = apply_hunks(original, fp.hunks)
                data = new_content.encode("utf-8")
                if len(data) > max_file_bytes:
                    raise FileTooLargeError(f"Patched file exceeds max_file_bytes: {target_abs}")
                target_abs.parent.mkdir(parents=True, exist_ok=True)
                target_abs.write_text(new_content, encoding="utf-8")
                bytes_written_total += len(data)

            changed.append(rel_path.as_posix())

        _append_run_event(
            {
                "op": "apply_patch",
                "root_dir": str(root_abs),
                "changed_files": changed,
                "bytes_written_total": bytes_written_total,
                "started_at": started_at,
                "finished_at": utc_now_iso(),
                "ok": True,
            }
        )
        return changed
    except Exception as exc:
        _append_run_event(
            {
                "op": "apply_patch",
                "root_dir": str(root_dir),
                "started_at": started_at,
                "finished_at": utc_now_iso(),
                "ok": False,
                "error": {"type": type(exc).__name__, "message": str(exc)},
            }
        )
        raise
