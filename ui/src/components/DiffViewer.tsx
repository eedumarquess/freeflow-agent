interface DiffViewerProps {
  diffText: string;
}

type DiffLineType = "header" | "remove" | "add" | "context";

function getDiffLineType(line: string): DiffLineType {
  const t = line.trimStart();
  if (t.startsWith("diff --git ") || t.startsWith("index ") || t.startsWith("--- ") || t.startsWith("+++ ") || /^@@\s/.test(t)) {
    return "header";
  }
  if (line.startsWith("-") && !line.startsWith("---")) {
    return "remove";
  }
  if (line.startsWith("+") && !line.startsWith("+++")) {
    return "add";
  }
  return "context";
}

export function DiffViewer({ diffText }: DiffViewerProps): JSX.Element {
  if (!diffText) {
    return (
      <section className="card">
        <h3>Diff</h3>
        <p>No diff available for this run.</p>
      </section>
    );
  }

  const lines = diffText.split("\n");
  return (
    <section className="card">
      <h3>Diff</h3>
      <div className="diff">
        {lines.map((line, i) => {
          const type = getDiffLineType(line);
          const key = `${i}-${type}-${line.slice(0, 20)}`;
          return (
            <div key={key} className={`diff-line diff-line--${type}`}>
              {line || "\u00A0"}
            </div>
          );
        })}
      </div>
    </section>
  );
}
