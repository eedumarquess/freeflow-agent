import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ArtifactsPanel } from "../components/ArtifactsPanel";
import { DiffViewer } from "../components/DiffViewer";
import { GateActions } from "../components/GateActions";
import { GraphView } from "../components/GraphView";
import { StatusBadge } from "../components/StatusBadge";
import { decideGate, getRun, getRunGraph, getRunMetrics, runNext } from "../lib/api";
import type { Gate, RunData, RunGraph, RunMetrics } from "../types";

function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) {
    return "-";
  }
  return `${seconds.toFixed(2)}s`;
}

export function RunDetailPage(): JSX.Element {
  const { runId = "" } = useParams();
  const [run, setRun] = useState<RunData | null>(null);
  const [graph, setGraph] = useState<RunGraph | null>(null);
  const [metrics, setMetrics] = useState<RunMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [decisionLoading, setDecisionLoading] = useState(false);
  const [nextLoading, setNextLoading] = useState(false);
  const [error, setError] = useState("");
  const [decisionMessage, setDecisionMessage] = useState("");

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [runData, graphData, metricsData] = await Promise.all([
        getRun(runId),
        getRunGraph(runId),
        getRunMetrics(runId),
      ]);
      setRun(runData);
      setGraph(graphData);
      setMetrics(metricsData);
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

  const onNext = useCallback(async () => {
    setNextLoading(true);
    setError("");
    try {
      await runNext(runId);
      await loadData();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setNextLoading(false);
    }
  }, [loadData, runId]);

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

  // If status already passed this gate, don't show it as pending (avoids double-approve)
  const rawPending = run.approvals_state?.pending_gate ?? null;
  const pendingGate =
    rawPending === "plan" && run.status === "APPROVED_PLAN"
      ? null
      : rawPending === "patch" && run.status === "APPROVED_PATCH"
        ? null
        : rawPending === "final" && run.status === "FINALIZED"
          ? null
          : rawPending;
  const diffText = run.context?.current_diff || run.edits?.patch_text || "";
  const canContinue =
    !pendingGate &&
    run.status !== "FINALIZED" &&
    run.status !== "FAILED";

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

      {canContinue && (
        <section className="card">
          <h3>Continuar processo</h3>
          <p>Avance o workflow até a próxima pausa ou fim. Pode demorar vários minutos.</p>
          <button
            type="button"
            disabled={nextLoading}
            onClick={() => void onNext()}
          >
            {nextLoading ? "Executando…" : "Continuar"}
          </button>
        </section>
      )}

      <section className="card">
        <h3>Metrics</h3>
        <p>Total duration: {formatDuration(metrics?.summary.total_duration_sec)}</p>
        <p>Loop iterations: {metrics?.summary.loop_iters ?? "-"}</p>
        <p>Test failures: {metrics?.summary.test_failures ?? "-"}</p>
        <p>Run failed: {metrics?.summary.run_failed ?? "-"}</p>
        <p>Total failures: {metrics?.summary.total_failures ?? "-"}</p>
        <table>
          <thead>
            <tr>
              <th>Node</th>
              <th>Count</th>
              <th>Total duration</th>
              <th>Avg duration</th>
            </tr>
          </thead>
          <tbody>
            {(metrics?.nodes ?? []).map((node) => (
              <tr key={node.node}>
                <td>{node.node}</td>
                <td>{node.count}</td>
                <td>{formatDuration(node.total_duration_sec)}</td>
                <td>{formatDuration(node.avg_duration_sec)}</td>
              </tr>
            ))}
            {!metrics?.nodes?.length && (
              <tr>
                <td colSpan={4}>No telemetry records.</td>
              </tr>
            )}
          </tbody>
        </table>
      </section>

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
