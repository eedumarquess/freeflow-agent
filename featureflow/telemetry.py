from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .time_utils import utc_now_iso

NODE_ORDER: tuple[str, ...] = (
    "LOAD_CONTEXT",
    "PLAN",
    "PROPOSE_CHANGES",
    "AWAIT_APPROVAL",
    "APPLY_CHANGES",
    "RUN_TESTS",
    "DIAGNOSE",
    "FIX_LOOP",
    "REGRESSION_RISK",
    "REVIEW",
    "FINALIZE",
)


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_iso_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_test_command(raw_command: Any) -> bool:
    if isinstance(raw_command, list):
        parts = [str(part).lower() for part in raw_command]
        return "pytest" in parts
    if isinstance(raw_command, str):
        return "pytest" in raw_command.lower()
    return False


def _event_id(payload: dict[str, Any]) -> str:
    key_payload = {
        "node": payload.get("node"),
        "started_at": payload.get("started_at"),
        "finished_at": payload.get("finished_at"),
        "status_before": payload.get("status_before"),
        "status_after": payload.get("status_after"),
    }
    raw = json.dumps(key_payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def _build_node_metrics(run_data: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    telemetry = run_data.get("telemetry")
    telemetry_map = telemetry if isinstance(telemetry, dict) else {}
    raw_node_stats = telemetry_map.get("node_stats")
    node_stats = raw_node_stats if isinstance(raw_node_stats, dict) else {}
    has_node_stats = bool(node_stats)

    ordered_nodes = list(NODE_ORDER)
    for node in sorted(node_stats.keys()):
        if node not in ordered_nodes:
            ordered_nodes.append(node)

    node_metrics: list[dict[str, Any]] = []
    for node in ordered_nodes:
        raw_stats = node_stats.get(node)
        stats = raw_stats if isinstance(raw_stats, dict) else {}
        count = _coerce_int(stats.get("count"), 0)
        total_duration = _coerce_float(stats.get("total_duration_sec"), None if count <= 0 else 0.0)
        if total_duration is not None and total_duration < 0:
            total_duration = 0.0
        avg_duration = None
        if total_duration is not None and count > 0:
            avg_duration = total_duration / count
        node_metrics.append(
            {
                "node": node,
                "count": count,
                "total_duration_sec": total_duration,
                "avg_duration_sec": avg_duration,
            }
        )
    return node_metrics, has_node_stats


def _total_duration_sec(run_data: dict[str, Any]) -> float | None:
    created = _parse_iso_utc(run_data.get("created_at"))
    updated = _parse_iso_utc(run_data.get("updated_at"))
    if created is None or updated is None:
        return None
    seconds = (updated - created).total_seconds()
    return seconds if seconds >= 0 else 0.0


def compute_metrics(run_data: dict[str, Any], run_report_text: str = "") -> dict[str, Any]:
    del run_report_text  # reserved for future enrichments derived from run-report.

    commands = run_data.get("commands")
    command_records = commands if isinstance(commands, list) else []
    test_failures = 0
    for record in command_records:
        if not isinstance(record, dict):
            continue
        if not _is_test_command(record.get("command")):
            continue
        exit_code = record.get("exit_code")
        if exit_code != 0:
            test_failures += 1

    run_failed = 1 if str(run_data.get("status", "")) == "FAILED" else 0
    loop_iters = _coerce_int(run_data.get("loop_iters"), 0)
    total_duration = _total_duration_sec(run_data)
    node_metrics, has_node_telemetry = _build_node_metrics(run_data)

    summary = {
        "total_duration_sec": total_duration,
        "loop_iters": loop_iters,
        "test_failures": test_failures,
        "run_failed": run_failed,
        "total_failures": test_failures + run_failed,
    }
    return {
        "run_id": str(run_data.get("run_id", "")),
        "status": str(run_data.get("status", "")),
        "generated_at": utc_now_iso(),
        "summary": summary,
        "failures": {
            "test_failures": test_failures,
            "run_failed": run_failed,
            "total_failures": test_failures + run_failed,
        },
        "nodes": node_metrics,
        "has_node_telemetry": has_node_telemetry,
    }


def write_metrics_json(
    run_id: str,
    outputs_dir: str,
    allowed_roots: list[str] | None = None,
    run_data: dict[str, Any] | None = None,
    run_report_text: str | None = None,
) -> Path:
    from .storage import read_run, validate_write_path

    data = run_data if isinstance(run_data, dict) else read_run(run_id, outputs_dir)
    report_text = run_report_text if isinstance(run_report_text, str) else ""
    if run_report_text is None:
        report_path = Path(outputs_dir) / run_id / "run-report.md"
        if report_path.exists():
            report_text = report_path.read_text(encoding="utf-8")
    metrics = compute_metrics(data, report_text)

    metrics_path = Path(outputs_dir) / run_id / "metrics.json"
    roots = allowed_roots or ["outputs"]
    validate_write_path(metrics_path, roots)
    tmp = metrics_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    tmp.replace(metrics_path)
    return metrics_path


def append_node_event(
    run_id: str,
    outputs_dir: str,
    node: str,
    started_at: str,
    finished_at: str,
    duration_sec: float,
    status_before: str,
    status_after: str,
    ok: bool,
    allowed_roots: list[str] | None = None,
) -> bool:
    from .storage import read_run, write_run

    run_data = read_run(run_id, outputs_dir)
    telemetry = run_data.get("telemetry")
    telemetry_map = telemetry if isinstance(telemetry, dict) else {}

    events_raw = telemetry_map.get("node_events")
    events = events_raw if isinstance(events_raw, list) else []
    payload = {
        "node": node,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_sec": max(0.0, float(duration_sec)),
        "status_before": status_before,
        "status_after": status_after,
        "ok": bool(ok),
    }
    payload["event_id"] = _event_id(payload)
    if any(isinstance(item, dict) and item.get("event_id") == payload["event_id"] for item in events):
        return False

    events.append(payload)
    telemetry_map["node_events"] = events

    stats_raw = telemetry_map.get("node_stats")
    stats = stats_raw if isinstance(stats_raw, dict) else {}
    node_stats_raw = stats.get(node)
    node_stats = node_stats_raw if isinstance(node_stats_raw, dict) else {}
    prev_count = _coerce_int(node_stats.get("count"), 0)
    prev_total = _coerce_float(node_stats.get("total_duration_sec"), 0.0) or 0.0
    node_stats["count"] = prev_count + 1
    node_stats["total_duration_sec"] = round(prev_total + payload["duration_sec"], 6)
    stats[node] = node_stats
    telemetry_map["node_stats"] = stats
    run_data["telemetry"] = telemetry_map
    write_run(run_id, outputs_dir, run_data, allowed_roots)
    return True
