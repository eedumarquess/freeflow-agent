from __future__ import annotations

from pathlib import Path

from .storage import validate_write_path


CHANGE_REQUEST_TEMPLATE = """# Change Request

## Objective
- 

## Scope
- 

## Out-of-scope
- 

## Likely Files
- 

## Business Rules
- 

## Done Criteria
- 
- Tests: 

## Risks
- 
"""


TEST_PLAN_TEMPLATE = """# Test Plan

## Manual Validation
- 

## Existing Tests
- 

## New Tests
- 
"""


RUN_REPORT_TEMPLATE = """# Run Report

## Summary
- 

## Commands
- 

## Results
- 
"""


RISK_REPORT_TEMPLATE = """# Risk Report

not yet calculated
"""


def _write_file(path: Path, content: str, allowed_roots: list[str]) -> None:
    validate_write_path(path, allowed_roots)
    path.write_text(content, encoding="utf-8")


def create_run_artifacts(run_id: str, outputs_dir: str, allowed_roots: list[str]) -> None:
    run_dir = Path(outputs_dir) / run_id
    files = {
        run_dir / "change-request.md": CHANGE_REQUEST_TEMPLATE,
        run_dir / "test-plan.md": TEST_PLAN_TEMPLATE,
        run_dir / "run-report.md": RUN_REPORT_TEMPLATE,
        run_dir / "risk-report.md": RISK_REPORT_TEMPLATE,
    }
    for path, content in files.items():
        _write_file(path, content, allowed_roots)
