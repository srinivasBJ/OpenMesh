import axios from "axios";
import type {
  OpenMeshGraph,
  OpenMeshNodeInspection,
  OpenMeshTimeline,
  OpenMeshTraceDetail,
  OpenMeshTraceSummary,
} from "@/types/openmesh";

const api = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL || "/api", timeout: 30000 });

export const agentsApi = {
  list: (params?: Record<string, string>) => api.get("/agents", { params }).then(r => r.data),
  get: (id: string) => api.get(`/agents/${id}`).then(r => r.data),
  spawn: (data: { name: string; role: string; guild_id?: string }) =>
    api.post("/agents/spawn", data).then(r => r.data),
  retire: (id: string) => api.delete(`/agents/${id}`).then(r => r.data),
  joinGuild: (agentId: string, guildId: string) =>
    api.post(`/agents/${agentId}/join-guild/${guildId}`).then(r => r.data),
};

export const feedApi = {
  list: (params?: Record<string, string | number>) => api.get("/feed", { params }).then(r => r.data),
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
  list: (limit?: number) => api.get("/events", { params: { limit } }).then(r => r.data),
};

export const statsApi = {
  get: () => api.get("/stats").then(r => r.data),
};

export const simulationApi = {
  tick: () => api.post("/simulation/tick").then(r => r.data),
};

export const openmeshApi = {
  events: (limit?: number) => api.get("/openmesh/events", { params: { limit } }).then(r => r.data),
  traces: (limit?: number) =>
    api.get<OpenMeshTraceSummary[]>("/openmesh/traces", { params: { limit } }).then(r => r.data),
  trace: (traceId: string) =>
    api.get<OpenMeshTraceDetail>(`/openmesh/traces/${encodeURIComponent(traceId)}`).then(r => r.data),
  graph: (params?: { limit?: number }) =>
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
  ecosystem: () => api.get("/openmesh/ecosystem").then(r => r.data),
  localLlmMetrics: () => api.get("/openmesh/local-llm/metrics").then(r => r.data),
};
