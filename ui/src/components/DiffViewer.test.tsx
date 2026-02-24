import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DiffViewer } from "./DiffViewer";

describe("DiffViewer", () => {
  it("shows message when diff is empty", () => {
    render(<DiffViewer diffText="" />);
    expect(screen.getByText("No diff available for this run.")).toBeInTheDocument();
  });

  it("renders diff lines with styling classes", () => {
    const sampleDiff = [
      "diff --git a/foo b/foo",
      "index 123..456",
      "--- a/foo",
      "+++ b/foo",
      "@@ -1,3 +1,4 @@",
      "-removed line",
      "+added line",
      " context line",
    ].join("\n");

    const { container } = render(<DiffViewer diffText={sampleDiff} />);

    expect(screen.getByText("Diff")).toBeInTheDocument();
    expect(screen.getByText("diff --git a/foo b/foo")).toBeInTheDocument();

    const diffEl = container.querySelector(".diff");
    expect(diffEl).toBeInTheDocument();

    const headers = diffEl!.querySelectorAll(".diff-line--header");
    expect(headers.length).toBeGreaterThanOrEqual(4); // diff --git, index, ---, +++, @@

    const removes = diffEl!.querySelectorAll(".diff-line--remove");
    expect(removes.length).toBe(1);
    expect(removes[0].textContent).toBe("-removed line");

    const adds = diffEl!.querySelectorAll(".diff-line--add");
    expect(adds.length).toBe(1);
    expect(adds[0].textContent).toBe("+added line");

    const contexts = diffEl!.querySelectorAll(".diff-line--context");
    expect(contexts.length).toBeGreaterThanOrEqual(1);
    expect(contexts[0].textContent).toBe(" context line");
  });
});
