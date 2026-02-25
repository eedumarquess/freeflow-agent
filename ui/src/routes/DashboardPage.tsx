import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { createRun, listRuns } from "../lib/api";
import { StatusBadge } from "../components/StatusBadge";
import type { RunData } from "../types";

function sortByUpdatedAt(items: RunData[]): RunData[] {
  return [...items].sort((a, b) => (b.updated_at ?? "").localeCompare(a.updated_at ?? ""));
}

function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) {
    return "-";
  }
  return `${seconds.toFixed(2)}s`;
}

export function DashboardPage(): JSX.Element {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<RunData[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [newRunStory, setNewRunStory] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  const refreshRuns = useCallback(() => {
    listRuns()
      .then((data) => setRuns(sortByUpdatedAt(data)))
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");
    listRuns()
      .then((data) => {
        if (alive) {
          setRuns(sortByUpdatedAt(data));
        }
      })
      .catch((err: Error) => {
        if (alive) {
          setError(err.message);
        }
      })
      .finally(() => {
        if (alive) {
          setLoading(false);
        }
      });
    return () => {
      alive = false;
    };
  }, []);

  const handleCreateRun = () => {
    const story = newRunStory.trim();
    if (!story) {
      setCreateError("Digite a descrição da story.");
      return;
    }
    setCreating(true);
    setCreateError("");
    createRun(story)
      .then((run) => {
        setNewRunStory("");
        refreshRuns();
        navigate(`/runs/${run.run_id}`);
      })
      .catch((err: Error) => {
        setCreateError(err.message);
      })
      .finally(() => {
        setCreating(false);
      });
  };

  const filtered = useMemo(
    () => runs.filter((run) => run.run_id.toLowerCase().includes(search.toLowerCase())),
    [runs, search],
  );

  return (
    <main className="page">
      <header>
        <h1>Freeflow Runs</h1>
        <p>Dashboard of workflow runs and approval gates.</p>
      </header>

      <section className="card">
        <h2>Iniciar nova run</h2>
        <p>Informe a story ou descrição da feature (como na CLI: <code>python -m cli.main run &quot;...&quot;</code>).</p>
        <label htmlFor="new-run-story">Story / descrição</label>
        <textarea
          id="new-run-story"
          value={newRunStory}
          onChange={(e) => setNewRunStory(e.target.value)}
          placeholder="Ex: Adicionar endpoint GET /health e testes"
          rows={3}
          disabled={creating}
        />
        {createError && <p className="error">{createError}</p>}
        <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
          <button
            type="button"
            className="btn-primary"
            onClick={handleCreateRun}
            disabled={creating}
          >
            {creating ? "Criando…" : "Criar run"}
          </button>
        </div>
      </section>

      <section className="card">
        <label htmlFor="search-run">Search run ID</label>
        <input
          id="search-run"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Type run ID..."
        />
      </section>

      {loading && <p>Loading runs...</p>}
      {error && <p className="error">{error}</p>}

      {!loading && !error && (
        <section className="card">
          <table>
            <thead>
              <tr>
                <th>Run</th>
                <th>Status</th>
                <th>Pending Gate</th>
                <th>Duration</th>
                <th>Loops</th>
                <th>Failures</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((run) => (
                <tr key={run.run_id}>
                  <td>
                    <Link to={`/runs/${run.run_id}`}>{run.run_id}</Link>
                  </td>
                  <td>
                    <StatusBadge status={run.status} />
                  </td>
                  <td>{run.approvals_state?.pending_gate ?? "-"}</td>
                  <td>{formatDuration(run.metrics_summary?.total_duration_sec)}</td>
                  <td>{run.metrics_summary?.loop_iters ?? "-"}</td>
                  <td>{run.metrics_summary?.total_failures ?? "-"}</td>
                  <td>{run.updated_at ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!filtered.length && <p>No runs found.</p>}
        </section>
      )}
    </main>
  );
}
