from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from featureflow.artifacts import create_run_artifacts
import featureflow.storage as storage
from featureflow.storage import STATUS_PLANNED, STATUS_WAITING_APPROVAL_PLAN, init_run, read_run, update_status
from web.api import app


def _set_runs_dir(monkeypatch, runs_dir: Path) -> None:
    monkeypatch.setattr("web.api._runs_dir", lambda: runs_dir)
    monkeypatch.setattr(
        "web.api.approve_gate",
        lambda run_id, outputs_dir, gate, approver="web": storage.approve_gate(
            run_id,
            outputs_dir,
            gate,
            approver=approver,
            allowed_roots=[str(runs_dir.parents[1])],
        ),
    )


def test_get_runs_returns_empty_when_dir_missing(tmp_path: Path, monkeypatch) -> None:
    runs_dir = tmp_path / "outputs" / "runs"
    _set_runs_dir(monkeypatch, runs_dir)
    client = TestClient(app)

    response = client.get("/runs")

    assert response.status_code == 200
    assert response.json() == []


def test_get_runs_lists_valid_run_json_items(tmp_path: Path, monkeypatch) -> None:
    runs_dir = tmp_path / "outputs" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    init_run("run_api_list", {"story": "list"}, str(runs_dir), [str(tmp_path)])
    (runs_dir / "junk").mkdir(parents=True, exist_ok=True)
    _set_runs_dir(monkeypatch, runs_dir)
    client = TestClient(app)

    response = client.get("/runs")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["run_id"] == "run_api_list"


def test_get_run_returns_404_when_missing(tmp_path: Path, monkeypatch) -> None:
    runs_dir = tmp_path / "outputs" / "runs"
    _set_runs_dir(monkeypatch, runs_dir)
    client = TestClient(app)

    response = client.get("/runs/nope")

    assert response.status_code == 404
    assert response.json()["detail"] == "Run not found"


def test_post_approve_success_transitions_and_persists_approval(tmp_path: Path, monkeypatch) -> None:
    runs_dir = tmp_path / "outputs" / "runs"
    run_id = "run_api_approve_ok"
    init_run(run_id, {"story": "approve"}, str(runs_dir), [str(tmp_path)])
    update_status(run_id, str(runs_dir), STATUS_PLANNED, [str(tmp_path)])
    update_status(run_id, str(runs_dir), STATUS_WAITING_APPROVAL_PLAN, [str(tmp_path)])
    _set_runs_dir(monkeypatch, runs_dir)
    client = TestClient(app)

    response = client.post(
        f"/runs/{run_id}/approve",
        json={"gate": "plan", "approved": True, "note": "ok"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["note"] == "ok"
    assert body["run"]["status"] == "APPROVED_PLAN"
    assert body["run"]["approvals"][-1]["gate"] == "plan"
    assert body["run"]["approvals"][-1]["approver"] == "web"


def test_post_approve_false_returns_422_and_does_not_mutate(tmp_path: Path, monkeypatch) -> None:
    runs_dir = tmp_path / "outputs" / "runs"
    run_id = "run_api_approve_false"
    init_run(run_id, {"story": "reject"}, str(runs_dir), [str(tmp_path)])
    update_status(run_id, str(runs_dir), STATUS_PLANNED, [str(tmp_path)])
    update_status(run_id, str(runs_dir), STATUS_WAITING_APPROVAL_PLAN, [str(tmp_path)])
    before = read_run(run_id, str(runs_dir))
    _set_runs_dir(monkeypatch, runs_dir)
    client = TestClient(app)

    response = client.post(
        f"/runs/{run_id}/approve",
        json={"gate": "plan", "approved": False, "note": "not now"},
    )

    after = read_run(run_id, str(runs_dir))
    assert response.status_code == 422
    assert response.json()["detail"] == "Only approved=true is supported"
    assert after == before


def test_post_approve_invalid_gate_returns_422(tmp_path: Path, monkeypatch) -> None:
    runs_dir = tmp_path / "outputs" / "runs"
    run_id = "run_api_bad_gate"
    init_run(run_id, {"story": "bad gate"}, str(runs_dir), [str(tmp_path)])
    _set_runs_dir(monkeypatch, runs_dir)
    client = TestClient(app)

    response = client.post(
        f"/runs/{run_id}/approve",
        json={"gate": "nope", "approved": True},
    )

    assert response.status_code == 422


def test_post_approve_wrong_status_returns_409(tmp_path: Path, monkeypatch) -> None:
    runs_dir = tmp_path / "outputs" / "runs"
    run_id = "run_api_wrong_status"
    init_run(run_id, {"story": "wrong state"}, str(runs_dir), [str(tmp_path)])
    _set_runs_dir(monkeypatch, runs_dir)
    client = TestClient(app)

    response = client.post(
        f"/runs/{run_id}/approve",
        json={"gate": "patch", "approved": True},
    )

    assert response.status_code == 409
    assert "Cannot approve gate" in response.json()["detail"]


def test_get_artifact_downloads_allowed_file(tmp_path: Path, monkeypatch) -> None:
    runs_dir = tmp_path / "outputs" / "runs"
    run_id = "run_api_artifact_ok"
    init_run(run_id, {"story": "artifact"}, str(runs_dir), [str(tmp_path)])
    create_run_artifacts(run_id, str(runs_dir), [str(tmp_path)])
    _set_runs_dir(monkeypatch, runs_dir)
    client = TestClient(app)

    response = client.get(f"/runs/{run_id}/artifacts/change-request.md")

    assert response.status_code == 200
    assert "attachment; filename=\"change-request.md\"" in response.headers.get("content-disposition", "")
    assert response.text.startswith("# Change Request")


def test_get_artifact_invalid_name_or_traversal_returns_404(tmp_path: Path, monkeypatch) -> None:
    runs_dir = tmp_path / "outputs" / "runs"
    run_id = "run_api_artifact_invalid"
    init_run(run_id, {"story": "artifact invalid"}, str(runs_dir), [str(tmp_path)])
    create_run_artifacts(run_id, str(runs_dir), [str(tmp_path)])
    _set_runs_dir(monkeypatch, runs_dir)
    client = TestClient(app)

    invalid = client.get(f"/runs/{run_id}/artifacts/run.json")
    traversal = client.get(f"/runs/{run_id}/artifacts/%2E%2E%2Fchange-request.md")

    assert invalid.status_code == 404
    assert traversal.status_code == 404


def test_get_artifact_missing_file_returns_404(tmp_path: Path, monkeypatch) -> None:
    runs_dir = tmp_path / "outputs" / "runs"
    run_id = "run_api_artifact_missing"
    init_run(run_id, {"story": "artifact missing"}, str(runs_dir), [str(tmp_path)])
    _set_runs_dir(monkeypatch, runs_dir)
    client = TestClient(app)

    response = client.get(f"/runs/{run_id}/artifacts/change-request.md")

    assert response.status_code == 404
    assert response.json()["detail"] == "Artifact not found"
