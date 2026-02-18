from __future__ import annotations

from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def configure_run_logging(
    run_id: str,
    outputs_dir: str,
    allowed_write_roots: list[str] | None = None,
) -> None:
    """Placeholder for run-scoped logging setup."""
    return None


def _normalize_patch_line(line: str) -> str:
    if line.endswith("\n"):
        return line[:-1]
    return line


def apply_patch(root: Path, unified_diff_text: str) -> list[str]:
    """
    Apply a unified diff to files relative to `root`.
    Supports the subset used by this project tests.
    """
    lines = unified_diff_text.splitlines(keepends=True)
    i = 0
    changed_files: list[str] = []

    while i < len(lines):
        line = lines[i]
        if not line.startswith("--- "):
            i += 1
            continue

        i += 1
        if i >= len(lines) or not lines[i].startswith("+++ "):
            raise ValueError("Invalid patch format: missing '+++' line")
        new_path = lines[i].strip().split(" ", 1)[1]
        if new_path.startswith("b/"):
            rel_path = new_path[2:]
        else:
            rel_path = new_path
        i += 1

        file_path = (root / rel_path).resolve()
        original = file_path.read_text(encoding="utf-8").splitlines()
        rebuilt: list[str] = []
        cursor = 0

        while i < len(lines) and lines[i].startswith("@@"):
            header = lines[i]
            i += 1
            try:
                old_chunk = header.split(" ")[1]
                old_start = int(old_chunk.split(",")[0][1:])
            except Exception as exc:  # pragma: no cover - defensive
                raise ValueError(f"Invalid hunk header: {header.strip()}") from exc

            target_index = max(old_start - 1, 0)
            rebuilt.extend(original[cursor:target_index])
            cursor = target_index

            while i < len(lines):
                hunk_line = lines[i]
                if hunk_line.startswith("@@") or hunk_line.startswith("--- "):
                    break
                if hunk_line.startswith("\\"):
                    i += 1
                    continue

                kind = hunk_line[:1]
                text = _normalize_patch_line(hunk_line[1:])

                if kind == " ":
                    if cursor >= len(original) or original[cursor] != text:
                        raise ValueError("Patch context mismatch")
                    rebuilt.append(original[cursor])
                    cursor += 1
                elif kind == "-":
                    if cursor >= len(original) or original[cursor] != text:
                        raise ValueError("Patch removal mismatch")
                    cursor += 1
                elif kind == "+":
                    rebuilt.append(text)
                else:
                    raise ValueError(f"Unsupported patch line: {hunk_line.strip()}")

                i += 1

        rebuilt.extend(original[cursor:])
        new_content = "\n".join(rebuilt)
        if rebuilt:
            new_content += "\n"
        file_path.write_text(new_content, encoding="utf-8")
        changed_files.append(rel_path.replace("\\", "/"))

    return changed_files
