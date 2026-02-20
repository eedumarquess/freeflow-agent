from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from featureflow.telemetry import compute_metrics, write_metrics_json
from featureflow.storage import (
    STATUS_FAILED,
    approve_gate,
    read_run,
    reject_gate,
)
from featureflow.workflow.graph import NODE_NAMES, route_from_status

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_ARTIFACTS = {
    "change-request.md",
    "test-plan.md",
    "run-report.md",
    "risk-report.md",
    "pr-comment.md",
}


class ApproveRequest(BaseModel):
    gate: Literal["plan", "patch", "final"]
    approved: bool
    note: str | None = None


def _runs_dir() -> Path:
    return Path("outputs") / "runs"


def _normalize_run_payload(data: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(data)
    context = normalized.get("context")
    if not isinstance(context, dict):
        context = {}
    context.setdefault("current_diff", "")
    normalized["context"] = context

    edits = normalized.get("edits")
    if not isinstance(edits, dict):
        edits = {}
    edits.setdefault("patch_text", "")
    normalized["edits"] = edits

    approvals_state = normalized.get("approvals_state")
    if not isinstance(approvals_state, dict):
        approvals_state = {}
    approvals_state.setdefault("pending_gate", None)
    normalized["approvals_state"] = approvals_state

    status_meta = normalized.get("status_meta")
    if not isinstance(status_meta, dict):
        status_meta = {}
    status_meta.setdefault("last_node", None)
    normalized["status_meta"] = status_meta

    metrics_summary = normalized.get("metrics_summary")
    if not isinstance(metrics_summary, dict):
        metrics_summary = {}
    normalized["metrics_summary"] = metrics_summary
    return normalized


def _graph_node_statuses(run_data: dict[str, Any]) -> list[dict[str, str]]:
    order = list(NODE_NAMES)
    status = str(run_data.get("status", ""))
    last_node = None
    status_meta = run_data.get("status_meta")
    if isinstance(status_meta, dict):
        raw_last_node = status_meta.get("last_node")
        if isinstance(raw_last_node, str) and raw_last_node in order:
            last_node = raw_last_node

    route = route_from_status({"status": status})
    current_node = route if route in order else None
    if status == "FINALIZED":
        current_node = "FINALIZE"
    if status == STATUS_FAILED and last_node:
        current_node = last_node

    current_idx = order.index(current_node) if current_node in order else None
    out: list[dict[str, str]] = []
    for idx, node in enumerate(order):
        node_status = "pending"
        if current_idx is not None:
            if idx < current_idx:
                node_status = "done"
            elif idx == current_idx:
                node_status = "current"
            else:
                node_status = "pending"
        if status == STATUS_FAILED and current_idx is not None and idx > current_idx:
            node_status = "blocked"
        if status == STATUS_FAILED and current_idx is None:
            node_status = "blocked"
        out.append({"id": node, "status": node_status})
    return out


def _run_report_text(runs_dir: Path, run_id: str) -> str:
    report_path = runs_dir / run_id / "run-report.md"
    if not report_path.exists():
        return ""
    try:
        return report_path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _allowed_roots_for_runs_dir(runs_dir: Path) -> list[str]:
    if len(runs_dir.parents) > 1:
        return [str(runs_dir.parents[1])]
    return [str(runs_dir.parent)]


def _metrics_for_run(run_id: str, run_data: dict[str, Any], runs_dir: Path) -> dict[str, Any]:
    report_text = _run_report_text(runs_dir, run_id)
    metrics = compute_metrics(run_data, report_text)
    try:
        write_metrics_json(
            run_id=run_id,
            outputs_dir=str(runs_dir),
            allowed_roots=_allowed_roots_for_runs_dir(runs_dir),
            run_data=run_data,
            run_report_text=report_text,
        )
    except Exception:
        # API responses should not fail when metrics export is temporarily unavailable.
        pass
    return metrics


@app.get("/runs")
def list_runs() -> list[dict]:
    runs_dir = _runs_dir()
    if not runs_dir.exists():
        return []

    items: list[dict] = []
    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir():
            continue
        run_file = run_dir / "run.json"
        if not run_file.exists():
            continue
        try:
            run_data = read_run(run_dir.name, str(runs_dir))
            normalized = _normalize_run_payload(run_data)
            metrics = _metrics_for_run(run_dir.name, run_data, runs_dir)
            normalized["metrics_summary"] = metrics.get("summary", {})
            items.append(normalized)
        except Exception:
            continue
    return items


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    runs_dir = _runs_dir()
    try:
        return _normalize_run_payload(read_run(run_id, str(runs_dir)))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc


@app.post("/runs/{run_id}/approve")
def approve_run_gate(run_id: str, payload: ApproveRequest) -> dict[str, Any]:
    runs_dir = _runs_dir()
    try:
        read_run(run_id, str(runs_dir))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc

    try:
        if payload.approved:
            run_data = approve_gate(run_id, str(runs_dir), payload.gate, approver="web")
            decision = "approved"
        else:
            run_data = reject_gate(
                run_id,
                str(runs_dir),
                payload.gate,
                approver="web",
                note=payload.note,
            )
            decision = "rejected"
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc
    except ValueError as exc:
        message = str(exc)
        if "Cannot approve gate" in message or "Cannot decide gate" in message:
            raise HTTPException(status_code=409, detail=message) from exc
        raise HTTPException(status_code=422, detail=message) from exc

    return {"run": _normalize_run_payload(run_data), "note": payload.note, "decision": decision}


@app.get("/runs/{run_id}/graph")
def get_run_graph(run_id: str) -> dict[str, Any]:
    runs_dir = _runs_dir()
    try:
        run_data = read_run(run_id, str(runs_dir))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc
    return {
        "run_id": run_id,
        "status": str(run_data.get("status", "")),
        "nodes": _graph_node_statuses(run_data),
    }


@app.get("/runs/{run_id}/metrics")
def get_run_metrics(run_id: str) -> dict[str, Any]:
    runs_dir = _runs_dir()
    try:
        run_data = read_run(run_id, str(runs_dir))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc
    return _metrics_for_run(run_id, run_data, runs_dir)


@app.get("/runs/{run_id}/artifacts/{name}")
def get_run_artifact(run_id: str, name: str) -> FileResponse:
    runs_dir = _runs_dir()
    try:
        read_run(run_id, str(runs_dir))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc

    if name not in ALLOWED_ARTIFACTS:
        raise HTTPException(status_code=404, detail="Artifact not found")

    artifact_path = runs_dir / run_id / name
    if not artifact_path.exists() or not artifact_path.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")

    return FileResponse(path=artifact_path, filename=name, media_type="text/markdown")
