from __future__ import annotations

from dataclasses import dataclass
import re

from .errors import PatchApplyError


@dataclass(frozen=True)
class Hunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[str]


@dataclass(frozen=True)
class FilePatch:
    old_path: str
    new_path: str
    hunks: list[Hunk]


_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def _strip_ab_prefix(p: str) -> str:
    if p.startswith("a/") or p.startswith("b/"):
        return p[2:]
    return p


def parse_unified_diff(text: str) -> list[FilePatch]:
    lines = text.splitlines()
    for line in lines:
        if line.startswith("GIT binary patch") or line.startswith("Binary files "):
            raise PatchApplyError("Binary patches are not supported")
        if line.startswith("rename from ") or line.startswith("rename to "):
            raise PatchApplyError("Rename/move patches are not supported")

    patches: list[FilePatch] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("diff --git "):
            i += 1
            continue
        if not line.startswith("--- "):
            i += 1
            continue

        old_raw = line[4:].strip()
        i += 1
        if i >= len(lines) or not lines[i].startswith("+++ "):
            raise PatchApplyError("Malformed diff: missing +++ header")
        new_raw = lines[i][4:].strip()
        i += 1

        old_path = old_raw.split("\t", 1)[0]
        new_path = new_raw.split("\t", 1)[0]

        hunks: list[Hunk] = []
        while i < len(lines):
            if lines[i].startswith("diff --git ") or lines[i].startswith("--- "):
                break
            if lines[i].startswith("@@ "):
                m = _HUNK_RE.match(lines[i])
                if not m:
                    raise PatchApplyError(f"Malformed hunk header: {lines[i]}")
                old_start = int(m.group(1))
                old_count = int(m.group(2) or "1")
                new_start = int(m.group(3))
                new_count = int(m.group(4) or "1")
                i += 1
                hunk_lines: list[str] = []
                while i < len(lines) and not lines[i].startswith("@@ "):
                    if lines[i].startswith("diff --git ") or lines[i].startswith("--- "):
                        break
                    hunk_lines.append(lines[i])
                    i += 1
                hunks.append(
                    Hunk(
                        old_start=old_start,
                        old_count=old_count,
                        new_start=new_start,
                        new_count=new_count,
                        lines=hunk_lines,
                    )
                )
                continue
            i += 1

        patches.append(FilePatch(old_path=old_path, new_path=new_path, hunks=hunks))

    if text.strip() and not patches:
        raise PatchApplyError("No file patches found in diff")
    return patches


def relpath_and_kind(fp: FilePatch) -> tuple[str, str]:
    old_is_null = fp.old_path == "/dev/null"
    new_is_null = fp.new_path == "/dev/null"
    if old_is_null and new_is_null:
        raise PatchApplyError("Invalid patch: both paths are /dev/null")

    if not old_is_null and not new_is_null:
        old_rel = _strip_ab_prefix(fp.old_path)
        new_rel = _strip_ab_prefix(fp.new_path)
        if old_rel != new_rel:
            raise PatchApplyError(f"Rename/move patches are not supported: {old_rel} -> {new_rel}")
        return old_rel, "modify"

    if old_is_null:
        return _strip_ab_prefix(fp.new_path), "add"
    return _strip_ab_prefix(fp.old_path), "delete"


def apply_hunks(original: str, hunks: list[Hunk]) -> str:
    had_trailing_newline = original.endswith("\n")
    lines = original.splitlines()
    delta = 0

    for hunk in hunks:
        expected_old = sum(1 for l in hunk.lines if l.startswith((" ", "-")))
        expected_new = sum(1 for l in hunk.lines if l.startswith((" ", "+")))
        if expected_old != hunk.old_count or expected_new != hunk.new_count:
            raise PatchApplyError("Hunk line counts do not match header")

        idx = (hunk.old_start - 1) + delta
        if idx < 0 or idx > len(lines):
            raise PatchApplyError("Hunk start is out of range")

        for hl in hunk.lines:
            if hl == r"\ No newline at end of file":
                continue
            if not hl:
                raise PatchApplyError("Malformed hunk line")
            tag, text = hl[0], hl[1:]
            if tag == " ":
                if idx >= len(lines) or lines[idx] != text:
                    raise PatchApplyError("Context mismatch while applying patch")
                idx += 1
            elif tag == "-":
                if idx >= len(lines) or lines[idx] != text:
                    raise PatchApplyError("Delete mismatch while applying patch")
                del lines[idx]
                delta -= 1
            elif tag == "+":
                lines.insert(idx, text)
                idx += 1
                delta += 1
            else:
                raise PatchApplyError(f"Unknown hunk tag: {tag!r}")

    new_content = "\n".join(lines)
    if lines and had_trailing_newline:
        new_content += "\n"
    return new_content

