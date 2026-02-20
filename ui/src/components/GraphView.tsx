import type { GraphNode } from "../types";

interface GraphViewProps {
  nodes: GraphNode[];
}

export function GraphView({ nodes }: GraphViewProps): JSX.Element {
  return (
    <section className="card">
      <h3>Workflow Graph</h3>
      <ul className="graph-list">
        {nodes.map((node) => (
          <li key={node.id} className={`graph-node graph-${node.status}`}>
            <span>{node.id}</span>
            <small>{node.status}</small>
          </li>
        ))}
      </ul>
    </section>
  );
}
