from __future__ import annotations

import json
from pathlib import Path

from featureflow.storage import STATUS_FAILED, STATUS_FINALIZED, init_run, read_run, write_run
from featureflow.telemetry import append_node_event, compute_metrics, write_metrics_json


def test_compute_metrics_for_legacy_run_without_node_telemetry() -> None:
    run_data = {
        "run_id": "legacy",
        "status": STATUS_FINALIZED,
        "created_at": "2026-02-20T10:00:00Z",
        "updated_at": "2026-02-20T10:00:05Z",
        "loop_iters": 0,
        "commands": [
            {"command": ["python", "-m", "pytest", "-q"], "exit_code": 0},
        ],
    }

    metrics = compute_metrics(run_data)

    assert metrics["summary"]["total_duration_sec"] == 5.0
    assert metrics["summary"]["test_failures"] == 0
    assert metrics["summary"]["run_failed"] == 0
    assert metrics["summary"]["total_failures"] == 0
    assert metrics["nodes"]
    assert all(node["total_duration_sec"] is None for node in metrics["nodes"])


def test_compute_metrics_counts_test_failures_and_terminal_failure() -> None:
    run_data = {
        "run_id": "fail",
        "status": STATUS_FAILED,
        "loop_iters": 3,
        "commands": [
            {"command": ["python", "-m", "pytest", "-q"], "exit_code": 1},
            {"command": ["git", "diff"], "exit_code": 1},
        ],
    }

    metrics = compute_metrics(run_data)

    assert metrics["summary"]["loop_iters"] == 3
    assert metrics["summary"]["test_failures"] == 1
    assert metrics["summary"]["run_failed"] == 1
    assert metrics["summary"]["total_failures"] == 2


def test_append_node_event_updates_stats_and_metrics_export(tmp_path: Path) -> None:
    outputs_dir = tmp_path / "outputs" / "runs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    run_id = "run_telemetry_events"
    init_run(run_id, {"story": "telemetry"}, str(outputs_dir), [str(tmp_path)])

    appended = append_node_event(
        run_id=run_id,
        outputs_dir=str(outputs_dir),
        node="PLAN",
        started_at="2026-02-20T10:00:00Z",
        finished_at="2026-02-20T10:00:01Z",
        duration_sec=1.0,
        status_before="PLANNED",
        status_after="WAITING_APPROVAL_PLAN",
        ok=True,
        allowed_roots=[str(tmp_path)],
    )
    duplicated = append_node_event(
        run_id=run_id,
        outputs_dir=str(outputs_dir),
        node="PLAN",
        started_at="2026-02-20T10:00:00Z",
        finished_at="2026-02-20T10:00:01Z",
        duration_sec=1.0,
        status_before="PLANNED",
        status_after="WAITING_APPROVAL_PLAN",
        ok=True,
        allowed_roots=[str(tmp_path)],
    )
    run_data = read_run(run_id, str(outputs_dir))
    run_data["status"] = STATUS_FINALIZED
    write_run(run_id, str(outputs_dir), run_data, [str(tmp_path)])
    metrics_path = write_metrics_json(run_id, str(outputs_dir), [str(tmp_path)])

    exported = json.loads(metrics_path.read_text(encoding="utf-8"))
    node_row = next(row for row in exported["nodes"] if row["node"] == "PLAN")

    assert appended is True
    assert duplicated is False
    assert node_row["count"] == 1
    assert node_row["total_duration_sec"] == 1.0
