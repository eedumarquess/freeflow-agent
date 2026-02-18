from __future__ import annotations

from datetime import datetime
from pathlib import Path

import typer

from featureflow.artifacts import create_run_artifacts
from featureflow.config import get_allowed_write_roots, load_config
from featureflow.ids import generate_run_id
from featureflow.shell import run_command
from featureflow.storage import init_run, read_run, write_run

app = typer.Typer(add_completion=False)


@app.command()
def init() -> None:
    """Initialize project config and outputs directory."""
    example_path = Path("featureflow.yaml.example")
    config_path = Path("featureflow.yaml")
    if not config_path.exists():
        if not example_path.exists():
            raise typer.BadParameter("featureflow.yaml.example not found")
        config_path.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")
    outputs_dir = Path("outputs") / "runs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    typer.echo("Initialized featureflow.yaml and outputs/runs/")


@app.command()
def run(story: str = typer.Option(..., "--story")) -> None:
    """Start a run: create run_id, run.json, and artifacts."""
    cfg = load_config()
    run_id = generate_run_id()
    outputs_dir = cfg["runs"]["outputs_dir"]
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
        )
        diff_result = run_command(
            ["git", "diff"],
            allowed_commands,
            run_id,
            outputs_dir,
            cfg["runs"]["timeout_seconds"],
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
def test(run_id: str = typer.Option(..., "--run-id")) -> None:
    """Run pytest via allowlist for a run_id."""
    cfg = load_config()
    outputs_dir = cfg["runs"]["outputs_dir"]
    allowed_commands = cfg["security"]["allowed_commands"]

    result = run_command(
        ["pytest", "-q"],
        allowed_commands,
        run_id,
        outputs_dir,
        cfg["runs"]["timeout_seconds"],
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


if __name__ == "__main__":
    app()
