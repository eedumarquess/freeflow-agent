interface DiffViewerProps {
  diffText: string;
}

export function DiffViewer({ diffText }: DiffViewerProps): JSX.Element {
  return (
    <section className="card">
      <h3>Diff</h3>
      {diffText ? (
        <pre className="diff">{diffText}</pre>
      ) : (
        <p>No diff available for this run.</p>
      )}
    </section>
  );
}
