import axios from "axios";
import type {
  OpenMeshGraph,
  OpenMeshNodeInspection,
  OpenMeshReplay,
  OpenMeshTimeline,
  OpenMeshTraceDetail,
  OpenMeshTraceSummary,
} from "@/types/openmesh";

const api = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL || "/api", timeout: 30000 });

export const agentsApi = {
  list: (params?: Record<string, string | undefined>) => api.get("/agents", { params }).then(r => r.data),
  get: (id: string) => api.get(`/agents/${id}`).then(r => r.data),
  spawn: (data: { name: string; role: string; guild_id?: string }) =>
    api.post("/agents/spawn", data).then(r => r.data),
  retire: (id: string) => api.delete(`/agents/${id}`).then(r => r.data),
  joinGuild: (agentId: string, guildId: string) =>
    api.post(`/agents/${agentId}/join-guild/${guildId}`).then(r => r.data),
};

export const feedApi = {
  list: (params?: Record<string, string | number | undefined>) => api.get("/feed", { params }).then(r => r.data),
  getComments: (postId: string) => api.get(`/feed/${postId}/comments`).then(r => r.data),
  react: (postId: string, emoji: string) =>
    api.post(`/feed/${postId}/react`, null, { params: { emoji } }).then(r => r.data),
};

export const guildsApi = {
  list: () => api.get("/guilds").then(r => r.data),
  create: (data: { name: string; description: string; domain: string; emoji: string; color: string }) =>
    api.post("/guilds", data).then(r => r.data),
};

export const wikiApi = {
  list: (params?: Record<string, string>) => api.get("/wiki", { params }).then(r => r.data),
  getPage: (slug: string) => api.get(`/wiki/${slug}`).then(r => r.data),
};

export const eventsApi = {
  list: (limit?: number, workspaceId?: string) =>
    api.get("/events", { params: { limit, workspace_id: workspaceId } }).then(r => r.data),
};

export const statsApi = {
  get: () => api.get("/stats").then(r => r.data),
};

export const simulationApi = {
  tick: () => api.post("/simulation/tick").then(r => r.data),
};

export interface ProviderSettingsState {
  configured: boolean;
  provider: string | null;
  provider_name?: string;
  model?: string;
  mode?: string;
  masked_key?: string | null;
  source?: "settings" | "environment";
}

export interface ProviderTestResult {
  provider: string;
  provider_name: string;
  connected: boolean;
  status: string;
  message: string;
}

export interface LiveStatus {
  backend: string;
  provider: { configured: boolean; provider: string | null; name: string | null; model: string | null; mode: string };
  agents: { active: number; running: boolean };
  runner: { running: boolean; tick_count: number; last_error: string | null };
  events_per_second: number;
  websocket_clients: number;
}

export const settingsApi = {
  getProvider: () => api.get<ProviderSettingsState>("/settings/provider").then(r => r.data),
  saveProvider: (data: { provider: string; api_key: string; model?: string }) =>
    api.post("/settings/provider", data).then(r => r.data),
  testProvider: (data: { provider: string; api_key: string; model?: string }) =>
    api.post<ProviderTestResult>("/settings/provider/test", data).then(r => r.data),
  clearProvider: () => api.delete("/settings/provider").then(r => r.data),
};

export const controlApi = {
  startAgents: () => api.post("/agents/start").then(r => r.data),
  stopAgents: () => api.post("/agents/stop").then(r => r.data),
  liveStatus: () => api.get<LiveStatus>("/status/live").then(r => r.data),
};

export interface WorkspaceSummary {
  id: string;
  name: string;
  kind: "standard" | "demo";
  description?: string | null;
  project_count: number;
  agent_count: number;
}

export interface ProviderStatusEntry {
  provider: string;
  name: string;
  is_local: boolean;
  configured: boolean;
  selected: boolean;
  default_model?: string;
  model?: string | null;
  source?: "settings" | "environment";
  masked_key?: string;
}

export interface DiscoveredModel {
  provider: string;
  model: string;
  metadata?: Record<string, unknown>;
}

export interface DemoStatus {
  active: boolean;
  running: boolean;
  paused: boolean;
  workspace: { id: string; name: string; kind: string } | null;
  agents: { id: string; name: string }[];
}

export const workspacesApi = {
  list: () => api.get<{ workspaces: WorkspaceSummary[] }>("/workspaces").then(r => r.data.workspaces),
  get: (id: string) => api.get(`/workspaces/${id}`).then(r => r.data),
  create: (data: { name: string; description?: string }) =>
    api.post("/workspaces", data).then(r => r.data),
  remove: (id: string) => api.delete(`/workspaces/${id}`).then(r => r.data),
  createProject: (data: {
    workspace_id?: string;
    workspace_name?: string;
    name: string;
    repository_path?: string;
    github_url?: string;
    provider?: string;
    model?: string;
    agent_type?: string;
  }) => api.post("/projects", data).then(r => r.data),
};

export const providersApi = {
  list: () =>
    api
      .get<{ providers: ProviderStatusEntry[]; selected: { provider: string; model: string | null } | null }>("/providers")
      .then(r => r.data),
  connect: (provider: string, data: { api_key: string; model?: string }) =>
    api.post<{ connected: boolean; models: DiscoveredModel[] }>(`/providers/${provider}/connect`, data).then(r => r.data),
  models: (provider: string) =>
    api.get<{ models: DiscoveredModel[] }>(`/providers/${provider}/models`).then(r => r.data.models),
  select: (data: { provider: string; model?: string }) =>
    api.post("/providers/select", data).then(r => r.data),
  disconnect: (provider: string) => api.delete(`/providers/${provider}`).then(r => r.data),
};

export const demoApi = {
  status: () => api.get<DemoStatus>("/demo/status").then(r => r.data),
  start: () => api.post("/demo/start").then(r => r.data),
  stop: () => api.post("/demo/stop").then(r => r.data),
  terminate: () => api.delete("/demo").then(r => r.data),
};

export const sessionApi = {
  start: (workspaceId?: string) =>
    api.post("/agents/session/start", { workspace_id: workspaceId }).then(r => r.data),
  pause: () => api.post("/agents/session/pause").then(r => r.data),
  resume: () => api.post("/agents/session/resume").then(r => r.data),
  terminate: () => api.post("/agents/session/terminate").then(r => r.data),
};

export const openmeshApi = {
  events: (limit?: number) => api.get("/openmesh/events", { params: { limit } }).then(r => r.data),
  traces: (limit?: number) =>
    api.get<OpenMeshTraceSummary[]>("/openmesh/traces", { params: { limit } }).then(r => r.data),
  trace: (traceId: string) =>
    api.get<OpenMeshTraceDetail>(`/openmesh/traces/${encodeURIComponent(traceId)}`).then(r => r.data),
  graph: (params?: { limit?: number; workspace_id?: string }) =>
    api.get<OpenMeshGraph>("/openmesh/graph", { params }).then(r => r.data),
  graphSearch: (params: { q: string; node_type?: string; relationship_type?: string; limit?: number }) =>
    api.get("/openmesh/graph/search", { params }).then(r => r.data),
  graphFilter: (params?: {
    node_type?: string;
    relationship_type?: string;
    q?: string;
    lifecycle_state?: string;
    limit?: number;
  }) => api.get<OpenMeshGraph>("/openmesh/graph/filter", { params }).then(r => r.data),
  graphExplore: (
    nodeId: string,
    params?: { depth?: number; direction?: string; relationship_type?: string; node_type?: string; q?: string; limit?: number },
  ) => api.get(`/openmesh/graph/explore/${encodeURIComponent(nodeId)}`, { params }).then(r => r.data),
  inspectNode: (nodeId: string, limit?: number) =>
    api.get<OpenMeshNodeInspection>(`/openmesh/inspect/${encodeURIComponent(nodeId)}`, { params: { limit } }).then(r => r.data),
  timeline: (limit?: number) =>
    api.get<OpenMeshTimeline>("/openmesh/timeline", { params: { limit } }).then(r => r.data),
  traceTimeline: (traceId: string, limit?: number) =>
    api.get<OpenMeshTimeline>(`/openmesh/timeline/trace/${encodeURIComponent(traceId)}`, { params: { limit } }).then(r => r.data),
  replayEcosystem: (params?: { control?: string; position?: number; timestamp?: string; event_id?: string; speed?: number; limit?: number }) =>
    api.get<OpenMeshReplay>("/openmesh/replay/ecosystem", { params }).then(r => r.data),
  replayTrace: (
    traceId: string,
    params?: { control?: string; position?: number; timestamp?: string; event_id?: string; speed?: number; limit?: number },
  ) => api.get<OpenMeshReplay>(`/openmesh/replay/trace/${encodeURIComponent(traceId)}`, { params }).then(r => r.data),
  replayWorkflow: (
    workflowId: string,
    params?: { control?: string; position?: number; timestamp?: string; event_id?: string; speed?: number; limit?: number },
  ) => api.get<OpenMeshReplay>(`/openmesh/replay/workflow/${encodeURIComponent(workflowId)}`, { params }).then(r => r.data),
  ecosystem: () => api.get("/openmesh/ecosystem").then(r => r.data),
  localLlmMetrics: () => api.get("/openmesh/local-llm/metrics").then(r => r.data),
  runtimeMetrics: () => api.get("/openmesh/runtime/metrics").then(r => r.data),
  nodes: () => api.get("/openmesh/nodes").then(r => r.data),
  nodeStatus: () => api.get("/openmesh/node/status").then(r => r.data),
  failures: () => api.get("/openmesh/failures").then(r => r.data),
  failureReport: () => api.get("/openmesh/failures/report").then(r => r.data),
  reputation: () => api.get("/openmesh/reputation").then(r => r.data),
  agentReputation: (agentId: string) => api.get(`/openmesh/reputation/${agentId}`).then(r => r.data),
  mcpMetrics: () => api.get("/openmesh/mcp/metrics").then(r => r.data),
  tools: () => api.get("/openmesh/tools").then(r => r.data),
  resources: () => api.get("/openmesh/resources").then(r => r.data),
  workflowMetrics: () => api.get("/openmesh/workflows/metrics").then(r => r.data),
};
