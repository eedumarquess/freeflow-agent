import { useState } from "react";

import type { Gate } from "../types";

interface GateActionsProps {
  pendingGate: Gate | null;
  loading: boolean;
  onDecision: (gate: Gate, approved: boolean, note: string) => Promise<void>;
}

const GATES: Gate[] = ["plan", "patch", "final"];

export function GateActions({ pendingGate, loading, onDecision }: GateActionsProps): JSX.Element {
  const [note, setNote] = useState("");

  if (!pendingGate) {
    return (
      <section className="card">
        <h3>Gate Actions</h3>
        <p>No pending gate for this run.</p>
      </section>
    );
  }

  return (
    <section className="card">
      <h3>Gate Actions</h3>
      <p>Pending gate: <strong>{pendingGate}</strong></p>
      <label htmlFor="gate-note">Note</label>
      <textarea
        id="gate-note"
        value={note}
        onChange={(event) => setNote(event.target.value)}
        placeholder="Optional note for approval/rejection"
        rows={3}
      />
      <div className="gate-grid">
        {GATES.map((gate) => {
          const enabled = gate === pendingGate;
          return (
            <div key={gate} className="gate-item">
              <span className="gate-label">{gate}</span>
              <button
                type="button"
                disabled={!enabled || loading}
                onClick={() => onDecision(gate, true, note)}
              >
                Approve
              </button>
              <button
                type="button"
                className="danger"
                disabled={!enabled || loading}
                onClick={() => onDecision(gate, false, note)}
              >
                Reject
              </button>
            </div>
          );
        })}
      </div>
    </section>
  );
}
