interface StatusBadgeProps {
  status: string;
}

export function StatusBadge({ status }: StatusBadgeProps): JSX.Element {
  const klass = status.toLowerCase().includes("failed")
    ? "status status-failed"
    : status.toLowerCase().includes("waiting")
      ? "status status-waiting"
      : status.toLowerCase().includes("final")
        ? "status status-final"
        : "status status-default";
  return <span className={klass}>{status}</span>;
}
