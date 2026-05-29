import axios from "axios";

const api = axios.create({ baseURL: "/api", timeout: 30000 });

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
  traces: () => api.get("/openmesh/traces").then(r => r.data),
  trace: (traceId: string) => api.get(`/openmesh/traces/${traceId}`).then(r => r.data),
  graph: () => api.get("/openmesh/graph").then(r => r.data),
};
