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
  | "framework"
  | "mcp_server"
  | "mcp_config"
  | "federation_node"
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

export interface OpenMeshGraphNode {
  id: string;
  type: string;
  name: string;
  category?: string;
  runtime?: string;
  metadata?: Record<string, unknown>;
  event_count?: number;
  relationship_count?: number;
  first_seen?: string;
  last_seen?: string;
  lifecycle_state?: string;
  validation_status?: string;
  provenance?: {
    event_ids?: string[];
    trace_ids?: string[];
    session_ids?: string[];
    first_seen?: string;
    last_seen?: string;
    first_event_id?: string;
    last_event_id?: string;
    observations?: Array<Record<string, unknown>>;
  };
}

export interface OpenMeshGraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  relationship_type?: string;
  event_count?: number;
  observation_count?: number;
  first_seen?: string;
  last_seen?: string;
  lifecycle_state?: string;
  validation_status?: string;
  provenance?: {
    source?: string;
    target?: string;
    relationship_type?: string;
    event_ids?: string[];
    trace_ids?: string[];
    session_ids?: string[];
    span_ids?: string[];
    first_seen?: string;
    last_seen?: string;
    first_event_id?: string;
    last_event_id?: string;
    observations?: Array<Record<string, unknown>>;
  };
}

export interface OpenMeshGraph {
  nodes: OpenMeshGraphNode[];
  edges: OpenMeshGraphEdge[];
  validation?: Record<string, unknown>;
}

export interface OpenMeshTraceSummary {
  trace_id: string;
  started_at?: string;
  ended_at?: string;
  event_count: number;
  agents?: string[];
  tools?: string[];
  status: string;
}

export interface OpenMeshTraceDetail extends OpenMeshTraceSummary {
  events: OpenMeshEvent[];
  relationships?: Array<{
    source: string;
    target: string;
    type: string;
    relationship_type?: string;
    trace_id?: string;
    event_id?: string;
    provenance?: OpenMeshGraphEdge["provenance"];
  }>;
}

export interface OpenMeshNodeInspection {
  node_id: string;
  node_type: string;
  node: OpenMeshGraphNode;
  first_seen?: string;
  last_seen?: string;
  event_count: number;
  relationship_count: number;
  trace_ids: string[];
  session_ids: string[];
  incoming_relationships: OpenMeshGraphEdge[];
  outgoing_relationships: OpenMeshGraphEdge[];
  provenance?: OpenMeshGraphNode["provenance"] & {
    relationship_event_count?: number;
  };
  validation?: Record<string, unknown>;
}

export interface OpenMeshTimeline {
  scope?: string;
  subject?: Record<string, unknown>;
  first_appearance?: string;
  last_appearance?: string;
  relationship_changes?: Array<Record<string, unknown>>;
  workflow_changes?: Array<Record<string, unknown>>;
  capability_changes?: Array<Record<string, unknown>>;
  mcp_changes?: Array<Record<string, unknown>>;
  session_history?: Array<Record<string, unknown>>;
  snapshot_history?: Array<Record<string, unknown>>;
  timeline?: Array<Record<string, unknown>>;
  summary?: Record<string, number>;
}
