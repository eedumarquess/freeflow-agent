import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";

import { getArtifact } from "../lib/api";

const ARTIFACTS = [
  "change-request.md",
  "test-plan.md",
  "run-report.md",
  "risk-report.md",
  "pr-comment.md",
  "plan.json",
  "refusal.json",
];

interface ArtifactsPanelProps {
  runId: string;
}

export function ArtifactsPanel({ runId }: ArtifactsPanelProps): JSX.Element {
  const [selected, setSelected] = useState<string>(ARTIFACTS[0]);
  const [content, setContent] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");
    getArtifact(runId, selected)
      .then((text) => {
        if (alive) {
          setContent(text);
        }
      })
      .catch((err: Error) => {
        if (alive) {
          setContent("");
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
  }, [runId, selected]);

  const isJsonArtifact = selected.endsWith(".json");
  let jsonContent = "";
  if (isJsonArtifact && content) {
    try {
      jsonContent = JSON.stringify(JSON.parse(content), null, 2);
    } catch {
      jsonContent = content;
    }
  }

  return (
    <section className="card">
      <h3>Artifacts</h3>
      <div className="artifact-tabs">
        {ARTIFACTS.map((name) => (
          <button
            key={name}
            type="button"
            className={selected === name ? "active" : ""}
            onClick={() => setSelected(name)}
          >
            {name}
          </button>
        ))}
      </div>
      {loading && <p>Loading artifact...</p>}
      {error && <p className="error">{error}</p>}
      {!loading && !error && !isJsonArtifact && (
        <div className="markdown">
          <ReactMarkdown>{content}</ReactMarkdown>
        </div>
      )}
      {!loading && !error && isJsonArtifact && (
        <pre className="artifact-json">
          <code>{jsonContent}</code>
        </pre>
      )}
    </section>
  );
}
