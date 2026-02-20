from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .storage import read_run, validate_write_path


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


PR_COMMENT_TEMPLATE = """# PR Comment

## Summary
- 

## Validation
- 

## Risk
- 
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
        run_dir / "pr-comment.md": PR_COMMENT_TEMPLATE,
    }
    for path, content in files.items():
        _write_file(path, content, allowed_roots)


def _command_log_key(command_record: dict) -> str:
    payload = {
        "command": command_record.get("command"),
        "started_at": command_record.get("started_at"),
        "finished_at": command_record.get("finished_at"),
        "exit_code": command_record.get("exit_code"),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def append_command_logs_to_run_report(
    run_id: str,
    outputs_dir: str,
    allowed_roots: list[str] | None = None,
) -> int:
    run_data = read_run(run_id, outputs_dir)
    commands = run_data.get("commands")
    if not isinstance(commands, list):
        return 0

    report_path = Path(outputs_dir) / run_id / "run-report.md"
    roots = allowed_roots or ["outputs"]
    validate_write_path(report_path, roots)
    existing = report_path.read_text(encoding="utf-8") if report_path.exists() else ""

    blocks: list[str] = []
    added = 0
    for record in commands:
        if not isinstance(record, dict):
            continue
        marker = f"<!-- command-log:{_command_log_key(record)} -->"
        if marker in existing:
            continue

        raw_cmd = record.get("command")
        if isinstance(raw_cmd, list):
            command_text = " ".join(str(part) for part in raw_cmd)
        else:
            command_text = str(raw_cmd or "")

        blocks.append(
            "\n".join(
                [
                    "",
                    f"## Command Log: `{command_text or '(unknown)'}`",
                    marker,
                    f"Started: {record.get('started_at', '')}",
                    f"Finished: {record.get('finished_at', '')}",
                    f"Exit code: {record.get('exit_code')}",
                    "Stdout:",
                    str(record.get("stdout", "")),
                    "Stderr:",
                    str(record.get("stderr", "")),
                    "",
                ]
            )
        )
        added += 1

    if blocks:
        report_path.write_text(existing + "".join(blocks), encoding="utf-8")
    return added
