from __future__ import annotations

from pathlib import Path

from featureflow.artifacts import create_run_artifacts


def test_create_run_artifacts_does_not_overwrite_existing_by_default(tmp_path: Path) -> None:
    outputs_dir = tmp_path / "outputs" / "runs"
    run_id = "run_idempotent_default"
    run_dir = outputs_dir / run_id

    create_run_artifacts(run_id, str(outputs_dir), [str(tmp_path)])
    report_path = run_dir / "run-report.md"
    report_path.write_text("custom run report", encoding="utf-8")

    create_run_artifacts(run_id, str(outputs_dir), [str(tmp_path)])
    assert report_path.read_text(encoding="utf-8") == "custom run report"


def test_create_run_artifacts_can_overwrite_when_requested(tmp_path: Path) -> None:
    outputs_dir = tmp_path / "outputs" / "runs"
    run_id = "run_idempotent_overwrite"
    run_dir = outputs_dir / run_id

    create_run_artifacts(run_id, str(outputs_dir), [str(tmp_path)])
    report_path = run_dir / "run-report.md"
    report_path.write_text("custom run report", encoding="utf-8")

    create_run_artifacts(run_id, str(outputs_dir), [str(tmp_path)], overwrite=True)
    assert "Run Report" in report_path.read_text(encoding="utf-8")
