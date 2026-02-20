from __future__ import annotations

from pathlib import Path

import typer

from featureflow.artifacts import append_command_logs_to_run_report, create_run_artifacts
from featureflow.config import get_allowed_write_roots, get_project_root, load_config
from featureflow.contracts import validate_change_request
from featureflow.fs_ops import apply_patch, configure_run_logging, inspect_patch_limits
from featureflow.ids import generate_run_id
from featureflow.shell import run_command
from featureflow.storage import (
    GATE_FINAL,
    GATE_PATCH,
    GATE_PLAN,
    STATUS_FAILED,
    STATUS_FINALIZED,
    STATUS_PATCH_PROPOSED,
    STATUS_TESTS_FAILED,
    STATUS_TESTS_PASSED,
    STATUS_TESTS_RUNNING,
    STATUS_WAITING_APPROVAL_FINAL,
    STATUS_WAITING_APPROVAL_PATCH,
    STATUS_WAITING_APPROVAL_PLAN,
    append_command,
    append_scope_warning,
    approve_gate,
    init_run,
    read_run,
    transition_status,
    write_run,
)
from featureflow.time_utils import utc_now_iso
from featureflow.workflow.engine import advance_until_pause_or_end

app = typer.Typer(add_completion=False)


def _run_tests_for_run(
    run_id: str,
    cfg: dict,
    root: Path,
    outputs_dir: str,
    allowed_roots: list[str],
) -> dict:
    allowed_commands = cfg["security"]["allowed_commands"]
    transition_status(run_id, outputs_dir, STATUS_TESTS_RUNNING, allowed_roots)

    try:
        result = run_command(
            ["pytest", "-q"],
            allowed_commands,
            None,
            outputs_dir,
            cfg["runs"]["timeout_seconds"],
            cwd=root,
            allowed_write_roots=allowed_roots,
        )
    except PermissionError as exc:
        now = utc_now_iso()
        result = {
            "command": ["pytest", "-q"],
            "started_at": now,
            "finished_at": now,
            "exit_code": 1,
            "stdout": "",
            "stderr": f"Command not allowed: {exc}",
            "timeout_seconds": cfg["runs"]["timeout_seconds"],
        }
    if "started_at" not in result or "finished_at" not in result:
        now = utc_now_iso()
        result.setdefault("started_at", now)
        result.setdefault("finished_at", now)
    result.setdefault("timeout_seconds", cfg["runs"]["timeout_seconds"])
    append_command(run_id, outputs_dir, result, allowed_roots)

    append_command_logs_to_run_report(run_id, outputs_dir, allowed_roots)

    data = read_run(run_id, outputs_dir)
    data["test_results"] = {
        "exit_code": result["exit_code"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
    }
    data["status"] = STATUS_TESTS_PASSED if result["exit_code"] == 0 else STATUS_TESTS_FAILED
    write_run(run_id, outputs_dir, data, allowed_roots)
    return data


def _print_gate_instruction(run_id: str, status: str) -> bool:
    if status == STATUS_WAITING_APPROVAL_PLAN:
        typer.echo(f"Next: run python -m cli.main approve --run-id {run_id} --gate {GATE_PLAN}")
        return True
    if status == STATUS_WAITING_APPROVAL_PATCH:
        typer.echo(f"Next: run python -m cli.main approve --run-id {run_id} --gate {GATE_PATCH}")
        return True
    if status == STATUS_WAITING_APPROVAL_FINAL:
        typer.echo(f"Next: run python -m cli.main approve --run-id {run_id} --gate {GATE_FINAL}")
        return True
    return False


@app.command()
def init() -> None:
    """Initialize project config and outputs directory."""
    root = get_project_root()
    example_path = root / "featureflow.yaml.example"
    config_path = root / "featureflow.yaml"
    if not config_path.exists():
        if not example_path.exists():
            raise typer.BadParameter("featureflow.yaml.example not found")
        config_path.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")
    outputs_dir = root / "outputs" / "runs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    typer.echo("Initialized featureflow.yaml and outputs/runs/")


@app.command()
def run(story: str = typer.Argument(..., help="Story or feature description for this run")) -> None:
    """Start a run: create run_id, run.json, and artifacts."""
    cfg = load_config()
    root = get_project_root()
    run_id = generate_run_id()
    outputs_dir = str(root / cfg["runs"]["outputs_dir"])
    allowed_roots = get_allowed_write_roots(cfg)

    init_run(run_id, {"story": story}, outputs_dir, allowed_roots)
    create_run_artifacts(run_id, outputs_dir, allowed_roots)
    advance_until_pause_or_end(run_id, cfg=cfg, root=root)
    status = read_run(run_id, outputs_dir).get("status", "")
    typer.echo(f"Run created: {run_id}")
    if not _print_gate_instruction(run_id, str(status)):
        typer.echo(f"Current status: {status}")


@app.command()
def approve(
    run_id: str = typer.Option(..., "--run-id", help="Run ID to approve"),
    gate: str = typer.Option(..., "--gate", help="Gate to approve: plan|patch|final"),
) -> None:
    """Approve a pending gate transition for a run."""
    cfg = load_config()
    root = get_project_root()
    outputs_dir = str(root / cfg["runs"]["outputs_dir"])
    allowed_roots = get_allowed_write_roots(cfg)

    normalized_gate = gate.strip().lower()
    try:
        data = approve_gate(
            run_id,
            outputs_dir,
            normalized_gate,
            approver="local",
            allowed_roots=allowed_roots,
        )
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc

    typer.echo(f"Gate approved: {normalized_gate}")
    typer.echo(f"Current status: {data['status']}")


@app.command("next")
def next_step(
    run_id: str = typer.Option(..., "--run-id", help="Run ID to inspect next action"),
) -> None:
    """Advance the run via LangGraph until pause point or terminal status."""
    cfg = load_config()
    root = get_project_root()
    outputs_dir = str(root / cfg["runs"]["outputs_dir"])
    data = read_run(run_id, outputs_dir)
    status = data.get("status")

    if _print_gate_instruction(run_id, str(status)):
        return
    if status == STATUS_FAILED:
        typer.echo("Run is in FAILED state.")
        return

    final_state = advance_until_pause_or_end(run_id, cfg=cfg, root=root)
    if _print_gate_instruction(run_id, final_state.status):
        return
    if final_state.status == STATUS_FINALIZED:
        typer.echo("Run is finalized.")
        return
    if final_state.status == STATUS_FAILED:
        data = read_run(run_id, outputs_dir)
        reason = data.get("failure_reason", "unknown")
        typer.echo(f"Run failed: {reason}")
        return
    typer.echo(f"Current status: {final_state.status}")


@app.command()
def test(
    run_id: str = typer.Argument(..., help="Run ID (e.g. from `python -m cli.main run`)"),
) -> None:
    """Run pytest via allowlist for a run_id."""
    cfg = load_config()
    root = get_project_root()
    outputs_dir = str(root / cfg["runs"]["outputs_dir"])
    allowed_roots = get_allowed_write_roots(cfg)
    try:
        _run_tests_for_run(run_id, cfg, root, outputs_dir, allowed_roots)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc

    typer.echo("Tests completed")


@app.command()
def validate(run_id: str = typer.Option(..., "--run-id", help="Run ID to validate contracts")) -> None:
    """Validate run contracts for a run_id."""
    cfg = load_config()
    root = get_project_root()
    outputs_dir = str(root / cfg["runs"]["outputs_dir"])

    change_request_path = Path(outputs_dir) / run_id / "change-request.md"
    ok, issues = validate_change_request(change_request_path)
    if ok:
        typer.echo("VALID")
        return

    typer.echo("INVALID")
    for issue in issues:
        typer.echo(f"- {issue}")
    raise typer.Exit(code=1)


@app.command()
def apply(
    run_id: str = typer.Argument(..., help="Run ID"),
    patch_file: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False),
) -> None:
    """Apply a unified diff after validating the run change contract."""
    cfg = load_config()
    root = get_project_root()
    outputs_dir = str(root / cfg["runs"]["outputs_dir"])
    allowed_roots = get_allowed_write_roots(cfg)

    run_data = read_run(run_id, outputs_dir)
    change_request_path = Path(outputs_dir) / run_id / "change-request.md"
    ok, issues = validate_change_request(change_request_path)
    if not ok:
        run_data["status"] = STATUS_FAILED
        run_data["failure_reason"] = "Invalid change-request.md contract"
        run_data["contract_issues"] = issues
        write_run(run_id, outputs_dir, run_data, allowed_roots)
        typer.echo("INVALID CONTRACT")
        for issue in issues:
            typer.echo(f"- {issue}")
        raise typer.Exit(code=1)

    configure_run_logging(run_id, outputs_dir, allowed_write_roots=allowed_roots)
    unified_diff_text = patch_file.read_text(encoding="utf-8")
    limits = inspect_patch_limits(unified_diff_text, cfg=cfg)
    if limits["violations"]:
        warning = {
            "kind": "small_diff_limit",
            "source": "CLI_APPLY",
            "created_at": utc_now_iso(),
            "details": limits,
        }
        append_scope_warning(run_id, outputs_dir, warning, allowed_roots)
        report_path = Path(outputs_dir) / run_id / "run-report.md"
        report = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
        report += (
            "\n## Scope Warning (CLI_APPLY)\n"
            f"- Diff lines: `{limits['diff_lines']}` (limit `{limits['max_diff_lines']}`)\n"
            f"- Files changed: `{limits['files_changed']}` (limit `{limits['max_files_changed']}`)\n"
        )
        for violation in limits["violations"]:
            report += f"- Violation `{violation.get('rule', 'unknown')}`: {violation.get('message', '')}\n"
        report_path.write_text(report, encoding="utf-8")

    changed_files = apply_patch(root, unified_diff_text, enforce_limits=False)

    try:
        transition_status(run_id, outputs_dir, STATUS_PATCH_PROPOSED, allowed_roots)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc

    run_data = read_run(run_id, outputs_dir)
    run_data["applied_files"] = changed_files
    edits = run_data.get("edits") if isinstance(run_data.get("edits"), dict) else {}
    edits["applied_files"] = changed_files
    edits.setdefault("patch_text", "")
    run_data["edits"] = edits
    run_data.pop("failure_reason", None)
    run_data.pop("contract_issues", None)
    write_run(run_id, outputs_dir, run_data, allowed_roots)

    typer.echo(f"Applied patch with {len(changed_files)} file(s) changed")


if __name__ == "__main__":
    app()
