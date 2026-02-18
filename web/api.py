from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException

from featureflow.storage import read_run

app = FastAPI()


@app.get("/runs")
def list_runs() -> list[dict]:
    runs_dir = Path("outputs") / "runs"
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
    runs_dir = Path("outputs") / "runs"
    try:
        return read_run(run_id, str(runs_dir))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc
