from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from featureflow.artifacts import create_run_artifacts
import featureflow.storage as storage
from featureflow.storage import (
    STATUS_APPROVED_PLAN,
    STATUS_FAILED,
    STATUS_FINALIZED,
    STATUS_PLANNED,
    STATUS_WAITING_APPROVAL_PATCH,
    STATUS_WAITING_APPROVAL_PLAN,
    append_command,
    init_run,
    read_run,
    update_status,
    write_run,
)
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
    monkeypatch.setattr(
        "web.api.reject_gate",
        lambda run_id, outputs_dir, gate, approver="web", note=None: storage.reject_gate(
            run_id,
            outputs_dir,
            gate,
            approver=approver,
            note=note,
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
    assert body["decision"] == "approved"
    assert body["run"]["status"] == "APPROVED_PLAN"
    assert body["run"]["approvals"][-1]["gate"] == "plan"
    assert body["run"]["approvals"][-1]["approver"] == "web"


def test_post_reject_moves_run_to_failed_and_persists_decision(tmp_path: Path, monkeypatch) -> None:
    runs_dir = tmp_path / "outputs" / "runs"
    run_id = "run_api_reject"
    init_run(run_id, {"story": "reject"}, str(runs_dir), [str(tmp_path)])
    update_status(run_id, str(runs_dir), STATUS_PLANNED, [str(tmp_path)])
    update_status(run_id, str(runs_dir), STATUS_WAITING_APPROVAL_PLAN, [str(tmp_path)])
    _set_runs_dir(monkeypatch, runs_dir)
    client = TestClient(app)

    response = client.post(
        f"/runs/{run_id}/approve",
        json={"gate": "plan", "approved": False, "note": "not now"},
    )

    after = read_run(run_id, str(runs_dir))
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "rejected"
    assert after["status"] == "FAILED"
    assert after["failure_reason"] == "Gate 'plan' rejected"
    assert after["approvals"][-1]["gate"] == "plan"
    assert after["approvals"][-1]["approved"] is False
    assert after["approvals"][-1]["note"] == "not now"


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


def test_post_reject_wrong_status_returns_409(tmp_path: Path, monkeypatch) -> None:
    runs_dir = tmp_path / "outputs" / "runs"
    run_id = "run_api_reject_wrong_status"
    init_run(run_id, {"story": "wrong state"}, str(runs_dir), [str(tmp_path)])
    _set_runs_dir(monkeypatch, runs_dir)
    client = TestClient(app)

    response = client.post(
        f"/runs/{run_id}/approve",
        json={"gate": "patch", "approved": False},
    )

    assert response.status_code == 409
    assert "Cannot decide gate" in response.json()["detail"]


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


def test_get_artifact_supports_plan_json_and_refusal_json(tmp_path: Path, monkeypatch) -> None:
    runs_dir = tmp_path / "outputs" / "runs"
    run_id = "run_api_artifact_json"
    init_run(run_id, {"story": "artifact json"}, str(runs_dir), [str(tmp_path)])
    run_output_dir = runs_dir / run_id
    run_output_dir.mkdir(parents=True, exist_ok=True)
    (run_output_dir / "plan.json").write_text('{"plan":"ok"}', encoding="utf-8")
    (run_output_dir / "refusal.json").write_text('{"refusal":"ok"}', encoding="utf-8")
    _set_runs_dir(monkeypatch, runs_dir)
    client = TestClient(app)

    plan_resp = client.get(f"/runs/{run_id}/artifacts/plan.json")
    refusal_resp = client.get(f"/runs/{run_id}/artifacts/refusal.json")

    assert plan_resp.status_code == 200
    assert plan_resp.headers["content-type"].startswith("application/json")
    assert plan_resp.text == '{"plan":"ok"}'
    assert refusal_resp.status_code == 200
    assert refusal_resp.headers["content-type"].startswith("application/json")
    assert refusal_resp.text == '{"refusal":"ok"}'


def test_get_run_includes_normalized_fields(tmp_path: Path, monkeypatch) -> None:
    runs_dir = tmp_path / "outputs" / "runs"
    run_id = "run_api_get_normalized"
    init_run(run_id, {"story": "normalize"}, str(runs_dir), [str(tmp_path)])
    _set_runs_dir(monkeypatch, runs_dir)
    client = TestClient(app)

    response = client.get(f"/runs/{run_id}")

    assert response.status_code == 200
    body = response.json()
    assert "context" in body and "current_diff" in body["context"]
    assert "edits" in body and "patch_text" in body["edits"]
    assert "approvals_state" in body and "pending_gate" in body["approvals_state"]
    assert "status_meta" in body and "last_node" in body["status_meta"]


def test_get_run_graph_returns_nodes(tmp_path: Path, monkeypatch) -> None:
    runs_dir = tmp_path / "outputs" / "runs"
    run_id = "run_api_graph_waiting"
    init_run(run_id, {"story": "graph"}, str(runs_dir), [str(tmp_path)])
    update_status(run_id, str(runs_dir), STATUS_PLANNED, [str(tmp_path)])
    update_status(run_id, str(runs_dir), STATUS_WAITING_APPROVAL_PLAN, [str(tmp_path)])
    _set_runs_dir(monkeypatch, runs_dir)
    client = TestClient(app)

    response = client.get(f"/runs/{run_id}/graph")

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == run_id
    assert body["status"] == STATUS_WAITING_APPROVAL_PLAN
    nodes = body["nodes"]
    assert isinstance(nodes, list)
    assert any(node["id"] == "AWAIT_APPROVAL" and node["status"] == "current" for node in nodes)


def test_get_run_graph_finalized_and_failed_states(tmp_path: Path, monkeypatch) -> None:
    runs_dir = tmp_path / "outputs" / "runs"
    run_id = "run_api_graph_failed"
    init_run(run_id, {"story": "graph fail"}, str(runs_dir), [str(tmp_path)])
    update_status(run_id, str(runs_dir), STATUS_PLANNED, [str(tmp_path)])
    update_status(run_id, str(runs_dir), STATUS_WAITING_APPROVAL_PLAN, [str(tmp_path)])
    storage.reject_gate(run_id, str(runs_dir), "plan", approver="web", allowed_roots=[str(tmp_path)])
    _set_runs_dir(monkeypatch, runs_dir)
    client = TestClient(app)

    failed_resp = client.get(f"/runs/{run_id}/graph")
    assert failed_resp.status_code == 200
    failed_nodes = failed_resp.json()["nodes"]
    assert any(node["status"] == "blocked" for node in failed_nodes)

    finalized_id = "run_api_graph_finalized"
    init_run(finalized_id, {"story": "graph ok"}, str(runs_dir), [str(tmp_path)])
    update_status(finalized_id, str(runs_dir), STATUS_PLANNED, [str(tmp_path)])
    update_status(finalized_id, str(runs_dir), STATUS_WAITING_APPROVAL_PLAN, [str(tmp_path)])
    storage.approve_gate(finalized_id, str(runs_dir), "plan", approver="web", allowed_roots=[str(tmp_path)])
    update_status(finalized_id, str(runs_dir), "PATCH_PROPOSED", [str(tmp_path)])
    update_status(finalized_id, str(runs_dir), "WAITING_APPROVAL_PATCH", [str(tmp_path)])
    storage.approve_gate(finalized_id, str(runs_dir), "patch", approver="web", allowed_roots=[str(tmp_path)])
    update_status(finalized_id, str(runs_dir), "TESTS_RUNNING", [str(tmp_path)])
    update_status(finalized_id, str(runs_dir), "TESTS_PASSED", [str(tmp_path)])
    update_status(finalized_id, str(runs_dir), "WAITING_APPROVAL_FINAL", [str(tmp_path)])
    storage.approve_gate(finalized_id, str(runs_dir), "final", approver="web", allowed_roots=[str(tmp_path)])
    final_resp = client.get(f"/runs/{finalized_id}/graph")
    assert final_resp.status_code == 200
    final_nodes = final_resp.json()["nodes"]
    assert any(node["id"] == "FINALIZE" and node["status"] == "current" for node in final_nodes)


def test_get_runs_includes_metrics_summary(tmp_path: Path, monkeypatch) -> None:
    runs_dir = tmp_path / "outputs" / "runs"
    run_id = "run_api_metrics_summary"
    init_run(run_id, {"story": "metrics"}, str(runs_dir), [str(tmp_path)])
    append_command(
        run_id,
        str(runs_dir),
        {
            "command": ["python", "-m", "pytest", "-q"],
            "started_at": "2026-02-20T10:00:00Z",
            "finished_at": "2026-02-20T10:00:03Z",
            "exit_code": 1,
            "stdout": "failed",
            "stderr": "",
            "timeout_seconds": 60,
        },
        [str(tmp_path)],
    )
    data = read_run(run_id, str(runs_dir))
    data["status"] = STATUS_FAILED
    data["loop_iters"] = 2
    data["created_at"] = "2026-02-20T10:00:00Z"
    data["updated_at"] = "2026-02-20T10:00:06Z"
    write_run(run_id, str(runs_dir), data, [str(tmp_path)])
    _set_runs_dir(monkeypatch, runs_dir)
    client = TestClient(app)

    response = client.get("/runs")

    assert response.status_code == 200
    runs = response.json()
    item = next(run for run in runs if run["run_id"] == run_id)
    assert item["metrics_summary"]["loop_iters"] == 2
    assert item["metrics_summary"]["test_failures"] == 1
    assert item["metrics_summary"]["run_failed"] == 1
    assert item["metrics_summary"]["total_failures"] == 2
    assert item["metrics_summary"]["total_duration_sec"] is not None
    assert item["metrics_summary"]["total_duration_sec"] >= 0


def test_get_run_metrics_returns_payload_and_exports_file(tmp_path: Path, monkeypatch) -> None:
    runs_dir = tmp_path / "outputs" / "runs"
    run_id = "run_api_metrics"
    init_run(run_id, {"story": "metrics endpoint"}, str(runs_dir), [str(tmp_path)])
    _set_runs_dir(monkeypatch, runs_dir)
    client = TestClient(app)

    response = client.get(f"/runs/{run_id}/metrics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == run_id
    assert payload["summary"]["loop_iters"] == 0
    assert payload["nodes"]
    assert all(node["total_duration_sec"] is None for node in payload["nodes"])
    assert (runs_dir / run_id / "metrics.json").exists()


def test_post_next_returns_404_when_run_missing(tmp_path: Path, monkeypatch) -> None:
    runs_dir = tmp_path / "outputs" / "runs"
    _set_runs_dir(monkeypatch, runs_dir)
    client = TestClient(app)

    response = client.post("/runs/missing_run/next")

    assert response.status_code == 404
    assert response.json()["detail"] == "Run not found"


def test_post_next_returns_409_when_waiting_approval(tmp_path: Path, monkeypatch) -> None:
    runs_dir = tmp_path / "outputs" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    run_id = "run_next_waiting"
    init_run(run_id, {"story": "next"}, str(runs_dir), [str(tmp_path)])
    update_status(run_id, str(runs_dir), STATUS_PLANNED, [str(tmp_path)])
    update_status(run_id, str(runs_dir), STATUS_WAITING_APPROVAL_PLAN, [str(tmp_path)])
    _set_runs_dir(monkeypatch, runs_dir)
    client = TestClient(app)

    response = client.post(f"/runs/{run_id}/next")

    assert response.status_code == 409
    assert "Approve the pending gate first" in response.json()["detail"]


def test_post_next_returns_409_when_failed(tmp_path: Path, monkeypatch) -> None:
    runs_dir = tmp_path / "outputs" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    run_id = "run_next_failed"
    init_run(run_id, {"story": "next"}, str(runs_dir), [str(tmp_path)])
    data = read_run(run_id, str(runs_dir))
    data["status"] = STATUS_FAILED
    write_run(run_id, str(runs_dir), data, [str(tmp_path)])
    _set_runs_dir(monkeypatch, runs_dir)
    client = TestClient(app)

    response = client.post(f"/runs/{run_id}/next")

    assert response.status_code == 409
    assert "failed or finalized" in response.json()["detail"]


def test_post_next_returns_409_when_finalized(tmp_path: Path, monkeypatch) -> None:
    runs_dir = tmp_path / "outputs" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    run_id = "run_next_finalized"
    init_run(run_id, {"story": "next"}, str(runs_dir), [str(tmp_path)])
    data = read_run(run_id, str(runs_dir))
    data["status"] = STATUS_FINALIZED
    write_run(run_id, str(runs_dir), data, [str(tmp_path)])
    _set_runs_dir(monkeypatch, runs_dir)
    client = TestClient(app)

    response = client.post(f"/runs/{run_id}/next")

    assert response.status_code == 409
    assert "failed or finalized" in response.json()["detail"]


def test_post_next_success_returns_updated_run(tmp_path: Path, monkeypatch) -> None:
    runs_dir = tmp_path / "outputs" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    run_id = "run_next_ok"
    init_run(run_id, {"story": "next"}, str(runs_dir), [str(tmp_path)])
    data = read_run(run_id, str(runs_dir))
    data["status"] = STATUS_APPROVED_PLAN
    write_run(run_id, str(runs_dir), data, [str(tmp_path)])
    _set_runs_dir(monkeypatch, runs_dir)

    def _mock_advance(run_id: str, **kwargs: object) -> None:
        data = read_run(run_id, str(runs_dir))
        data["status"] = STATUS_WAITING_APPROVAL_PATCH
        data["approvals_state"] = {"pending_gate": "patch"}
        write_run(run_id, str(runs_dir), data, [str(tmp_path)])

    monkeypatch.setattr("web.api.advance_until_pause_or_end", _mock_advance)
    client = TestClient(app)

    response = client.post(f"/runs/{run_id}/next")

    assert response.status_code == 200
    body = response.json()
    assert body["run"]["run_id"] == run_id
    assert body["run"]["status"] == STATUS_WAITING_APPROVAL_PATCH
    assert body["run"]["approvals_state"].get("pending_gate") == "patch"
