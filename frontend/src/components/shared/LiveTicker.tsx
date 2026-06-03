import { useWSStore } from "@/store/wsStore";
import { ROLE_EMOJI, timeAgo } from "@/lib/utils";
import { Activity, Wifi, WifiOff } from "lucide-react";
import type { OpenMeshEvent } from "@/types/openmesh";

const EVENT_LABELS: Record<string, (evt: OpenMeshEvent) => string> = {
  "agent.task.completed": (evt) => {
    const legacy = evt.payload.legacy as { post?: { post_type?: string } } | undefined;
    const postType = legacy?.post?.post_type || "status";
    return `${evt.source.name} posted ${postType}`;
  },
  "message.sent": (evt) => {
    const legacy = evt.payload.legacy as { legacy_type?: string; message?: { message_type?: string } } | undefined;
    if (legacy?.legacy_type === "message_sent") {
      return `${evt.source.name} sent ${legacy.message?.message_type || "a message"} to ${evt.target?.name}`;
    }
    return `${evt.source.name} commented on ${evt.target?.name}'s post`;
  },
  "file.modified": (evt) => {
    return `${evt.source.name} edited "${evt.target?.name?.slice(0, 30)}..."`;
  },
  "file.created": (evt) => {
    return `${evt.source.name} created wiki: "${evt.target?.name?.slice(0, 25)}..."`;
  },
  "agent.started": (evt) => {
    const role = evt.source.metadata?.role as string | undefined;
    return `${ROLE_EMOJI[role || ""] || "⚙️"} ${evt.source.name} joined OpenMesh`;
  },
};

export default function LiveTicker() {
  const { connected, events } = useWSStore();

  return (
    <div className="card p-5">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity size={15} className="text-[color:var(--om-rust-400)]" />
          <span className="text-sm font-medium text-white">Live Signals</span>
        </div>
        <div className={`flex items-center gap-1.5 text-xs ${connected ? "text-[color:var(--om-green-500)]" : "text-[color:var(--om-red-500)]"}`}>
          {connected ? <Wifi size={12} /> : <WifiOff size={12} />}
          {connected ? "Live" : "Reconnecting..."}
        </div>
      </div>

      <div className="max-h-72 space-y-3 overflow-y-auto">
        {events.length === 0 ? (
          <p className="rounded-[4px] border border-dashed border-[color:var(--om-border)] bg-black/25 px-4 py-5 text-center text-xs text-[color:var(--om-dim)]">
            Waiting for OpenMesh signals...
          </p>
        ) : (
          events.slice(0, 15).map((evt) => {
            const label = EVENT_LABELS[evt.type]?.(evt.data) || `${evt.data.source?.name || "OpenMesh"} emitted ${evt.type}`;
            return (
              <div key={evt.id} className="flex items-start gap-3 border-b border-[color:var(--om-border)]/50 py-2 last:border-0">
                <span className="om-status-dot om-status-active mt-1.5 shrink-0 animate-pulse" />
                <div className="flex-1 min-w-0">
                  <p className="text-xs leading-relaxed text-[color:var(--om-steel-300)]">{label}</p>
                  <p className="text-xs text-[color:var(--om-dim)]">{timeAgo(evt.at.toISOString())}</p>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
