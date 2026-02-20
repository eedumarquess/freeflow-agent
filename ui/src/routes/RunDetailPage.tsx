import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ArtifactsPanel } from "../components/ArtifactsPanel";
import { DiffViewer } from "../components/DiffViewer";
import { GateActions } from "../components/GateActions";
import { GraphView } from "../components/GraphView";
import { StatusBadge } from "../components/StatusBadge";
import { decideGate, getRun, getRunGraph } from "../lib/api";
import type { Gate, RunData, RunGraph } from "../types";

export function RunDetailPage(): JSX.Element {
  const { runId = "" } = useParams();
  const [run, setRun] = useState<RunData | null>(null);
  const [graph, setGraph] = useState<RunGraph | null>(null);
  const [loading, setLoading] = useState(true);
  const [decisionLoading, setDecisionLoading] = useState(false);
  const [error, setError] = useState("");
  const [decisionMessage, setDecisionMessage] = useState("");

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [runData, graphData] = await Promise.all([getRun(runId), getRunGraph(runId)]);
      setRun(runData);
      setGraph(graphData);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const onDecision = useCallback(
    async (gate: Gate, approved: boolean, note: string) => {
      setDecisionLoading(true);
      setDecisionMessage("");
      setError("");
      try {
        const result = await decideGate(runId, gate, approved, note);
        setDecisionMessage(`Gate ${gate} ${result.decision}.`);
        await loadData();
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setDecisionLoading(false);
      }
    },
    [loadData, runId],
  );

  if (loading) {
    return <p className="page">Loading run details...</p>;
  }

  if (error) {
    return (
      <main className="page">
        <p className="error">{error}</p>
        <Link to="/">Back</Link>
      </main>
    );
  }

  if (!run) {
    return (
      <main className="page">
        <p className="error">Run not found.</p>
        <Link to="/">Back</Link>
      </main>
    );
  }

  const pendingGate = run.approvals_state?.pending_gate ?? null;
  const diffText = run.context?.current_diff || run.edits?.patch_text || "";

  return (
    <main className="page">
      <header className="detail-header">
        <div>
          <Link to="/">Back</Link>
          <h1>Run {run.run_id}</h1>
        </div>
        <StatusBadge status={run.status} />
      </header>

      <section className="card">
        <h3>Metadata</h3>
        <p>Created: {run.created_at ?? "-"}</p>
        <p>Updated: {run.updated_at ?? "-"}</p>
        <p>Last node: {run.status_meta?.last_node ?? "-"}</p>
        <p>Message: {run.status_meta?.message ?? "-"}</p>
        {run.failure_reason && <p className="error">Failure: {run.failure_reason}</p>}
      </section>

      {decisionMessage && <p className="success">{decisionMessage}</p>}

      <GateActions pendingGate={pendingGate} loading={decisionLoading} onDecision={onDecision} />

      <section className="card">
        <h3>Approvals</h3>
        <ul>
          {(run.approvals ?? []).map((approval, idx) => (
            <li key={`${approval.approved_at}-${idx}`}>
              {approval.gate} - {approval.approved === false ? "rejected" : "approved"} - {approval.approver}
            </li>
          ))}
          {!run.approvals?.length && <li>No approval records.</li>}
        </ul>
      </section>

      <section className="card">
        <h3>Commands</h3>
        <ul>
          {(run.commands ?? []).map((cmd, idx) => (
            <li key={idx}>
              exit={cmd.exit_code ?? "-"} -{" "}
              {Array.isArray(cmd.command) ? cmd.command.join(" ") : (cmd.command ?? "(unknown)")}
            </li>
          ))}
          {!run.commands?.length && <li>No command execution records.</li>}
        </ul>
      </section>

      <ArtifactsPanel runId={run.run_id} />
      <DiffViewer diffText={diffText} />
      {graph && <GraphView nodes={graph.nodes} />}
    </main>
  );
}
