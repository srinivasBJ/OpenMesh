export type OpenMeshNodeType =
  | "agent"
  | "tool"
  | "model"
  | "memory"
  | "file"
  | "command"
  | "browser"
  | "user"
  | "service"
  | "runtime"
  | "process"
  | "workflow"
  | "capability"
  | "guild"
  | "wiki"
  | "post";

export type OpenMeshSeverity = "debug" | "info" | "warning" | "error";

export interface OpenMeshNode {
  node_id: string;
  node_type: OpenMeshNodeType;
  name: string;
  runtime?: string;
  metadata?: Record<string, unknown>;
}

export interface OpenMeshEvent {
  spec_version: "0.1";
  event_id: string;
  event_type: string;
  timestamp: string;
  workspace_id?: string;
  session_id?: string;
  trace_id?: string;
  span_id?: string;
  parent_span_id?: string;
  parent_event_id?: string;
  root_event_id?: string;
  source: OpenMeshNode;
  target?: OpenMeshNode;
  payload: Record<string, unknown>;
  metrics?: Record<string, unknown>;
  links?: Array<{
    url?: string;
    label?: string;
    trace_id?: string;
    span_id?: string;
    event_id?: string;
    relationship?: string;
    [key: string]: unknown;
  }>;
  severity?: OpenMeshSeverity;
}
