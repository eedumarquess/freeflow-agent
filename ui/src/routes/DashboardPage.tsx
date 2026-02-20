import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { listRuns } from "../lib/api";
import { StatusBadge } from "../components/StatusBadge";
import type { RunData } from "../types";

function sortByUpdatedAt(items: RunData[]): RunData[] {
  return [...items].sort((a, b) => (b.updated_at ?? "").localeCompare(a.updated_at ?? ""));
}

export function DashboardPage(): JSX.Element {
  const [runs, setRuns] = useState<RunData[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

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
