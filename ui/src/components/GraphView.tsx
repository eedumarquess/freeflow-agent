import type { GraphNode, GraphNodeState } from "../types";

interface GraphViewProps {
  nodes: GraphNode[];
}

function NodeIcon({ status }: { status: GraphNodeState }): JSX.Element | null {
  switch (status) {
    case "done":
      return (
        <svg
          aria-hidden
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <polyline points="20 6 9 17 4 12" />
        </svg>
      );
    case "blocked":
      return (
        <svg
          aria-hidden
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      );
    case "current":
      return (
        <svg
          aria-hidden
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
        >
          <circle cx="12" cy="12" r="10" strokeOpacity="0.25" />
          <path d="M12 2a10 10 0 0 1 10 10" />
        </svg>
      );
    case "pending":
    default:
      return null;
  }
}

const GRID_ORDER: string[] = [
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
];

function ArrowRight(): JSX.Element {
  return (
    <svg
      aria-hidden
      className="workflow-cell-arrow"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M5 12h14M12 5l7 7-7 7" />
    </svg>
  );
}

export function GraphView({ nodes }: GraphViewProps): JSX.Element {
  const nodeMap = new Map(nodes.map((n) => [n.id, n]));
  return (
    <section className="card">
      <h3>Workflow Graph</h3>
      <div className="workflow-grid" role="img" aria-label="Fluxo do workflow">
        {GRID_ORDER.map((id, index) => {
          const node = nodeMap.get(id);
          const hasNext = index < GRID_ORDER.length - 1;
          const isLastRow = index >= 9;
          if (!node)
            return (
              <div
                key={id}
                className={`workflow-grid-cell workflow-grid-cell--empty ${isLastRow ? "workflow-grid-cell--last-row" : ""}`}
              />
            );
          return (
            <div
              key={node.id}
              className={`workflow-grid-cell ${hasNext ? "workflow-grid-cell--has-next" : ""} ${isLastRow ? "workflow-grid-cell--last-row" : ""}`}
            >
              <span className={`workflow-node workflow-node--${node.status}`}>
                <NodeIcon status={node.status} />
              </span>
              <span className="workflow-node-label">{node.id}</span>
              {hasNext && <ArrowRight />}
            </div>
          );
        })}
      </div>
    </section>
  );
}
