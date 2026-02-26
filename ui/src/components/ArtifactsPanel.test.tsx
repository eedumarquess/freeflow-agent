import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ArtifactsPanel } from "./ArtifactsPanel";
import * as api from "../lib/api";

vi.mock("../lib/api");

describe("ArtifactsPanel", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders markdown artifacts by default", async () => {
    vi.mocked(api.getArtifact).mockResolvedValue("# Change Request\n\ncontent");

    render(<ArtifactsPanel runId="run-1" />);

    expect(await screen.findByText("Change Request")).toBeInTheDocument();
    expect(api.getArtifact).toHaveBeenCalledWith("run-1", "change-request.md");
  });

  it("renders json artifacts as formatted code", async () => {
    vi.mocked(api.getArtifact).mockImplementation(async (_runId: string, name: string) => {
      if (name === "plan.json") {
        return '{"plan":"ok","items":[1,2]}';
      }
      return "# Change Request\n\ncontent";
    });

    const { container } = render(<ArtifactsPanel runId="run-1" />);
    await screen.findByText("Change Request");

    fireEvent.click(screen.getByRole("button", { name: "plan.json" }));

    await waitFor(() => {
      expect(api.getArtifact).toHaveBeenCalledWith("run-1", "plan.json");
    });
    expect(container.querySelector("pre code")?.textContent).toContain('"plan": "ok"');
  });
});
