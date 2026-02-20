export type Gate = "plan" | "patch" | "final";

export type GraphNodeState = "done" | "current" | "pending" | "blocked";

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
