import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { RunDetailPage } from "./RunDetailPage";
import * as api from "../lib/api";

vi.mock("../lib/api");

function renderDetailRoute(): void {
  render(
    <MemoryRouter initialEntries={["/runs/run-1"]}>
      <Routes>
        <Route path="/runs/:runId" element={<RunDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("RunDetailPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders run detail and workflow graph", async () => {
    vi.mocked(api.getRun).mockResolvedValue({
      run_id: "run-1",
      status: "WAITING_APPROVAL_PLAN",
      created_at: "2026-02-20T10:00:00Z",
      updated_at: "2026-02-20T11:00:00Z",
      approvals_state: { pending_gate: "plan" },
      context: { current_diff: "diff --git a/x b/x" },
      edits: { patch_text: "" },
      status_meta: { last_node: "AWAIT_APPROVAL", message: "Waiting for PLAN approval." },
      approvals: [],
      commands: [],
    });
    vi.mocked(api.getRunGraph).mockResolvedValue({
      run_id: "run-1",
      status: "WAITING_APPROVAL_PLAN",
      nodes: [
        { id: "LOAD_CONTEXT", status: "done" },
        { id: "PLAN", status: "done" },
        { id: "AWAIT_APPROVAL", status: "current" },
      ],
    });
    vi.mocked(api.getRunMetrics).mockResolvedValue({
      run_id: "run-1",
      status: "WAITING_APPROVAL_PLAN",
      generated_at: "2026-02-20T11:00:00Z",
      summary: {
        total_duration_sec: 60,
        loop_iters: 0,
        test_failures: 0,
        run_failed: 0,
        total_failures: 0,
      },
      failures: {
        test_failures: 0,
        run_failed: 0,
        total_failures: 0,
      },
      has_node_telemetry: true,
      nodes: [{ node: "PLAN", count: 1, total_duration_sec: 0.2, avg_duration_sec: 0.2 }],
    });
    vi.mocked(api.getArtifact).mockResolvedValue("# Change Request");
    vi.mocked(api.decideGate).mockResolvedValue({
      decision: "approved",
      run: {
        run_id: "run-1",
        status: "APPROVED_PLAN",
      },
    });

    renderDetailRoute();

    expect(await screen.findByText("Run run-1")).toBeInTheDocument();
    expect(screen.getByText("AWAIT_APPROVAL", { selector: ".workflow-node-label" })).toBeInTheDocument();
    expect(await screen.findByText("Change Request")).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: "Approve" })[0]);
    await waitFor(() => {
      expect(api.decideGate).toHaveBeenCalledWith("run-1", "plan", true, "");
    });
  });

  it("can reject pending gate", async () => {
    vi.mocked(api.getRun).mockResolvedValue({
      run_id: "run-1",
      status: "WAITING_APPROVAL_PATCH",
      approvals_state: { pending_gate: "patch" },
      context: { current_diff: "" },
      edits: { patch_text: "" },
      approvals: [],
      commands: [],
    });
    vi.mocked(api.getRunGraph).mockResolvedValue({
      run_id: "run-1",
      status: "WAITING_APPROVAL_PATCH",
      nodes: [{ id: "AWAIT_APPROVAL", status: "current" }],
    });
    vi.mocked(api.getRunMetrics).mockResolvedValue({
      run_id: "run-1",
      status: "WAITING_APPROVAL_PATCH",
      generated_at: "2026-02-20T11:00:00Z",
      summary: {
        total_duration_sec: 10,
        loop_iters: 0,
        test_failures: 0,
        run_failed: 0,
        total_failures: 0,
      },
      failures: {
        test_failures: 0,
        run_failed: 0,
        total_failures: 0,
      },
      has_node_telemetry: false,
      nodes: [{ node: "PLAN", count: 0, total_duration_sec: null, avg_duration_sec: null }],
    });
    vi.mocked(api.getArtifact).mockResolvedValue("# Change Request");
    vi.mocked(api.decideGate).mockResolvedValue({
      decision: "rejected",
      run: {
        run_id: "run-1",
        status: "FAILED",
      },
    });

    renderDetailRoute();
    expect(await screen.findByText("Run run-1")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "Reject" })[1]);

    await waitFor(() => {
      expect(api.decideGate).toHaveBeenCalledWith("run-1", "patch", false, "");
    });
  });
});
