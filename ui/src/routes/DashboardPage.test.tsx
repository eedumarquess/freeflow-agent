import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DashboardPage } from "./DashboardPage";
import * as api from "../lib/api";

vi.mock("../lib/api");

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders runs and links to detail", async () => {
    vi.mocked(api.listRuns).mockResolvedValue([
      {
        run_id: "run-older",
        status: "CREATED",
        updated_at: "2026-02-20T10:00:00Z",
        approvals_state: { pending_gate: null },
      },
      {
        run_id: "run-newer",
        status: "WAITING_APPROVAL_PLAN",
        updated_at: "2026-02-20T12:00:00Z",
        approvals_state: { pending_gate: "plan" },
      },
    ]);

    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("run-newer")).toBeInTheDocument();
    expect(screen.getByText("run-older")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "run-newer" });
    expect(link).toHaveAttribute("href", "/runs/run-newer");
  });
});
