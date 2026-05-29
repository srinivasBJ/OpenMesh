import { create } from "zustand";
import type { OpenMeshEvent } from "@/types/openmesh";

interface LiveEvent {
  id: string;
  type: string;
  data: OpenMeshEvent;
  at: Date;
}

interface WSStore {
  connected: boolean;
  events: LiveEvent[];
  ws: WebSocket | null;
  connect: () => void;
  disconnect: () => void;
  clearEvents: () => void;
}

export const useWSStore = create<WSStore>((set, get) => ({
  connected: false,
  events: [],
  ws: null,

  connect: () => {
    if (get().ws) return;
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

    ws.onopen = () => {
      set({ connected: true });
      // Keep alive ping
      const ping = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "ping" }));
        } else {
          clearInterval(ping);
        }
      }, 25000);
    };

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        const openMeshEvent = normalizeOpenMeshEvent(data);
        if (openMeshEvent.event_type === "system.pong" || openMeshEvent.event_type === "system.connected") return;

        const event: LiveEvent = {
          id: openMeshEvent.event_id,
          type: openMeshEvent.event_type,
          data: openMeshEvent,
          at: new Date(openMeshEvent.timestamp),
        };
        set((s) => ({ events: [event, ...s.events].slice(0, 50) }));
      } catch {}
    };

    ws.onclose = () => {
      set({ connected: false, ws: null });
      // Reconnect after 5s
      setTimeout(() => get().connect(), 5000);
    };

    ws.onerror = () => ws.close();

    set({ ws });
  },

  disconnect: () => {
    get().ws?.close();
    set({ ws: null, connected: false });
  },

  clearEvents: () => set({ events: [] }),
}));

function normalizeOpenMeshEvent(data: any): OpenMeshEvent {
  if (data?.spec_version === "0.1" && data?.event_type && data?.source) {
    return data as OpenMeshEvent;
  }

  const legacyAgent = data?.agent as { id?: string; name?: string; role?: string } | undefined;
  return {
    spec_version: "0.1",
    event_id: Math.random().toString(36).slice(2),
    event_type: data?.type || "system.event",
    timestamp: new Date().toISOString(),
    source: {
      node_id: legacyAgent?.id || "openmeshai.backend",
      node_type: legacyAgent?.id ? "agent" : "service",
      name: legacyAgent?.name || "OpenMeshAI Backend",
      runtime: "legacy.websocket",
      metadata: legacyAgent?.role ? { role: legacyAgent.role } : undefined,
    },
    payload: {
      legacy_type: data?.type,
      legacy: data || {},
    },
    metrics: {},
    links: [],
    severity: "info",
  };
}
