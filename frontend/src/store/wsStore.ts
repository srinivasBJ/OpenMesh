import { create } from "zustand";

interface LiveEvent {
  id: string;
  type: string;
  data: Record<string, unknown>;
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
        if (data.type === "pong" || data.type === "connected") return;

        const event: LiveEvent = {
          id: Math.random().toString(36).slice(2),
          type: data.type,
          data,
          at: new Date(),
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
