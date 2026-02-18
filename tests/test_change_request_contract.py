from __future__ import annotations

from pathlib import Path

from featureflow.contracts import MAX_CHANGE_REQUEST_BYTES, validate_change_request


def _valid_change_request() -> str:
    return """# Change Request

## Objective:
Implement contract validation.

## Scope:
Validate change-request and fail before patch apply.

## Out-of-scope:
No changes to web endpoints.

## Definition of done:
Validation exists, gate exists, and tests pass.

## Risks:
False positives if sections are too strict.
"""


def test_missing_file_fails(tmp_path: Path) -> None:
    ok, issues = validate_change_request(tmp_path / "change-request.md")
    assert ok is False
    assert any("File not found" in issue for issue in issues)


def test_missing_required_sections_fails(tmp_path: Path) -> None:
    path = tmp_path / "change-request.md"
    path.write_text(
        """# Change Request

## Objective:
Implement something.
""",
        encoding="utf-8",
    )

    ok, issues = validate_change_request(path)
    assert ok is False
    assert any("Missing required section: Scope" in issue for issue in issues)
    assert any("Missing required section: Risks" in issue for issue in issues)


def test_placeholder_only_sections_fail(tmp_path: Path) -> None:
    path = tmp_path / "change-request.md"
    path.write_text(
        """Objective: TODO
Scope: -
Out-of-scope: TBD
Done criteria: N/A
Risks: na
""",
        encoding="utf-8",
    )

    ok, issues = validate_change_request(path)
    assert ok is False
    assert any("placeholder content: Objective" in issue for issue in issues)
    assert any("placeholder content: Risks" in issue for issue in issues)


def test_complete_sections_pass(tmp_path: Path) -> None:
    path = tmp_path / "change-request.md"
    path.write_text(_valid_change_request(), encoding="utf-8")

    ok, issues = validate_change_request(path)
    assert ok is True
    assert issues == []


def test_file_too_large_fails(tmp_path: Path) -> None:
    path = tmp_path / "change-request.md"
    path.write_text("A" * (MAX_CHANGE_REQUEST_BYTES + 1), encoding="utf-8")

    ok, issues = validate_change_request(path)
    assert ok is False
    assert any("File is too large" in issue for issue in issues)
