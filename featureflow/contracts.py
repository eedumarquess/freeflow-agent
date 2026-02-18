from __future__ import annotations

from pathlib import Path
import re

MAX_CHANGE_REQUEST_BYTES = 64 * 1024

_PLACEHOLDERS = {"todo", "tbd", "-", "n/a", "na"}

_SECTION_ALIASES = {
    "objective": ("objective",),
    "scope": ("scope",),
    "out_of_scope": ("out of scope",),
    "definition_of_done": ("definition of done", "done criteria"),
    "risks": ("risks", "risk"),
}

_SECTION_TITLES = {
    "objective": "Objective",
    "scope": "Scope",
    "out_of_scope": "Out of scope",
    "definition_of_done": "Definition of done",
    "risks": "Risks",
}


def _normalize_label(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", label.lower()).strip()


def _match_section(label: str) -> str | None:
    normalized = _normalize_label(label)
    for section, aliases in _SECTION_ALIASES.items():
        if normalized in aliases:
            return section
    return None


def _extract_section_start(line: str) -> tuple[str | None, str]:
    stripped = line.strip()
    if not stripped:
        return None, ""

    if stripped.startswith("#"):
        label = stripped.lstrip("#").strip()
        return _match_section(label), ""

    match = re.match(r"^([A-Za-z][A-Za-z\s\-]+):\s*(.*)$", stripped)
    if not match:
        return None, ""

    label = match.group(1).strip()
    inline = match.group(2).strip()
    return _match_section(label), inline


def _is_placeholder_line(line: str) -> bool:
    text = re.sub(r"^\s*[-*+]\s*", "", line.strip())
    text = re.sub(r"^\d+\.\s*", "", text)
    if not text:
        return True
    return _normalize_label(text) in _PLACEHOLDERS


def _has_meaningful_content(lines: list[str]) -> bool:
    non_empty = [line for line in lines if line.strip()]
    if not non_empty:
        return False
    return any(not _is_placeholder_line(line) for line in non_empty)


def validate_change_request(path: str | Path) -> tuple[bool, list[str]]:
    issues: list[str] = []
    file_path = Path(path)

    if not file_path.exists():
        return False, [f"File not found: {file_path}"]

    size = file_path.stat().st_size
    if size == 0:
        issues.append("File is empty")
    if size > MAX_CHANGE_REQUEST_BYTES:
        issues.append(
            f"File is too large: {size} bytes (max {MAX_CHANGE_REQUEST_BYTES} bytes)"
        )

    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        issues.append("File must be valid UTF-8 text")
        return False, issues

    sections: dict[str, list[str]] = {}
    current_section: str | None = None
    for line in content.splitlines():
        section_start, inline_content = _extract_section_start(line)
        if section_start is not None:
            current_section = section_start
            sections.setdefault(section_start, [])
            if inline_content:
                sections[section_start].append(inline_content)
            continue

        if current_section is not None:
            sections[current_section].append(line)

    for section in _SECTION_TITLES:
        if section not in sections:
            issues.append(f"Missing required section: {_SECTION_TITLES[section]}")
            continue
        if not _has_meaningful_content(sections[section]):
            issues.append(
                f"Section has empty or placeholder content: {_SECTION_TITLES[section]}"
            )

    return len(issues) == 0, issues
