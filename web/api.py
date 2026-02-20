from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from featureflow.storage import approve_gate, read_run

app = FastAPI()

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
            items.append(read_run(run_dir.name, str(runs_dir)))
        except Exception:
            continue
    return items


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    runs_dir = _runs_dir()
    try:
        return read_run(run_id, str(runs_dir))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc


@app.post("/runs/{run_id}/approve")
def approve_run_gate(run_id: str, payload: ApproveRequest) -> dict[str, Any]:
    runs_dir = _runs_dir()
    try:
        read_run(run_id, str(runs_dir))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc

    if payload.approved is False:
        raise HTTPException(status_code=422, detail="Only approved=true is supported")

    try:
        run_data = approve_gate(run_id, str(runs_dir), payload.gate, approver="web")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc
    except ValueError as exc:
        message = str(exc)
        if "Cannot approve gate" in message:
            raise HTTPException(status_code=409, detail=message) from exc
        raise HTTPException(status_code=422, detail=message) from exc

    return {"run": run_data, "note": payload.note}


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
