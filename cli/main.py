from __future__ import annotations

from datetime import datetime
from pathlib import Path

import typer

from featureflow.artifacts import create_run_artifacts
from featureflow.config import get_allowed_write_roots, get_project_root, load_config
from featureflow.contracts import validate_change_request
from featureflow.fs_ops import apply_patch, configure_run_logging
from featureflow.ids import generate_run_id
from featureflow.shell import run_command
from featureflow.storage import init_run, read_run, write_run

app = typer.Typer(add_completion=False)


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

    # Optional git status + diff
    allowed_commands = cfg["security"]["allowed_commands"]
    try:
        status_result = run_command(
            ["git", "status", "--porcelain"],
            allowed_commands,
            run_id,
            outputs_dir,
            cfg["runs"]["timeout_seconds"],
            cwd=root,
        )
        diff_result = run_command(
            ["git", "diff"],
            allowed_commands,
            run_id,
            outputs_dir,
            cfg["runs"]["timeout_seconds"],
            cwd=root,
        )
        report_path = Path(outputs_dir) / run_id / "run-report.md"
        report = report_path.read_text(encoding="utf-8")
        report += (
            "\n## Git Status\n" + status_result["stdout"] + "\n"
            "\n## Git Diff\n" + diff_result["stdout"] + "\n"
        )
        report_path.write_text(report, encoding="utf-8")
    except PermissionError:
        pass

    typer.echo(f"Run created: {run_id}")


@app.command()
def test(run_id: str = typer.Argument(..., help="Run ID (e.g. from `ff run`)")) -> None:
    """Run pytest via allowlist for a run_id."""
    cfg = load_config()
    root = get_project_root()
    outputs_dir = str(root / cfg["runs"]["outputs_dir"])
    allowed_commands = cfg["security"]["allowed_commands"]

    result = run_command(
        ["pytest", "-q"],
        allowed_commands,
        run_id,
        outputs_dir,
        cfg["runs"]["timeout_seconds"],
        cwd=root,
    )

    report_path = Path(outputs_dir) / run_id / "run-report.md"
    report = report_path.read_text(encoding="utf-8")
    report += (
        "\n## Test Results\n"
        f"Exit code: {result['exit_code']}\n"
        f"Stdout:\n{result['stdout']}\n"
        f"Stderr:\n{result['stderr']}\n"
    )
    report_path.write_text(report, encoding="utf-8")

    data = read_run(run_id, outputs_dir)
    data["test_results"] = {
        "exit_code": result["exit_code"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
    }
    write_run(run_id, outputs_dir, data)

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
        run_data["status"] = "FAILED_CONTRACT"
        run_data["failure_reason"] = "Invalid change-request.md contract"
        run_data["contract_issues"] = issues
        write_run(run_id, outputs_dir, run_data, allowed_roots)
        typer.echo("INVALID CONTRACT")
        for issue in issues:
            typer.echo(f"- {issue}")
        raise typer.Exit(code=1)

    configure_run_logging(run_id, outputs_dir, allowed_write_roots=allowed_roots)
    unified_diff_text = patch_file.read_text(encoding="utf-8")
    changed_files = apply_patch(root, unified_diff_text)

    run_data = read_run(run_id, outputs_dir)
    run_data["status"] = "APPLIED"
    run_data["applied_files"] = changed_files
    run_data.pop("failure_reason", None)
    run_data.pop("contract_issues", None)
    write_run(run_id, outputs_dir, run_data, allowed_roots)

    typer.echo(f"Applied patch with {len(changed_files)} file(s) changed")


if __name__ == "__main__":
    app()
