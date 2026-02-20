export type Gate = "plan" | "patch" | "final";

export type GraphNodeState = "done" | "current" | "pending" | "blocked";

export interface RunMetricsSummary {
  total_duration_sec: number | null;
  loop_iters: number;
  test_failures: number;
  run_failed: number;
  total_failures: number;
}

export interface NodeMetric {
  node: string;
  count: number;
  total_duration_sec: number | null;
  avg_duration_sec: number | null;
}

export interface RunMetrics {
  run_id: string;
  status: string;
  generated_at: string;
  summary: RunMetricsSummary;
  failures: {
    test_failures: number;
    run_failed: number;
    total_failures: number;
  };
  nodes: NodeMetric[];
  has_node_telemetry: boolean;
}

export interface ApprovalEvent {
  gate: Gate;
  approved?: boolean;
  approved_at: string;
  approver: string;
  note?: string;
}

export interface RunData {
  run_id: string;
  status: string;
  created_at?: string;
  updated_at?: string;
  failure_reason?: string;
  approvals?: ApprovalEvent[];
  commands?: Array<{
    command?: string[] | string;
    exit_code?: number;
    stdout?: string;
    stderr?: string;
    started_at?: string;
    finished_at?: string;
  }>;
  context?: {
    current_diff?: string;
  };
  edits?: {
    patch_text?: string;
  };
  approvals_state?: {
    pending_gate?: Gate | null;
  };
  status_meta?: {
    last_node?: string | null;
    message?: string;
  };
  metrics_summary?: Partial<RunMetricsSummary>;
}

export interface GraphNode {
  id: string;
  status: GraphNodeState;
}

export interface RunGraph {
  run_id: string;
  status: string;
  nodes: GraphNode[];
}
