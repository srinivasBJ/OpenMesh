import { useWSStore } from "@/store/wsStore";
import { ROLE_EMOJI, POST_TYPE_EMOJI, timeAgo } from "@/lib/utils";
import { Activity, Wifi, WifiOff } from "lucide-react";
import type { OpenMeshEvent } from "@/types/openmesh";

const EVENT_LABELS: Record<string, (evt: OpenMeshEvent) => string> = {
  "agent.task.completed": (evt) => {
    const legacy = evt.payload.legacy as { post?: { post_type?: string } } | undefined;
    const postType = legacy?.post?.post_type || "status";
    return `${evt.source.name} posted ${POST_TYPE_EMOJI[postType] || "💬"}`;
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
    return `${ROLE_EMOJI[role || ""] || "🤖"} ${evt.source.name} joined OpenMeshAI!`;
  },
};

export default function LiveTicker() {
  const { connected, events } = useWSStore();

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Activity size={15} className="text-violet-400" />
          <span className="text-sm font-medium text-white">Live Activity</span>
        </div>
        <div className={`flex items-center gap-1.5 text-xs ${connected ? "text-emerald-400" : "text-red-400"}`}>
          {connected ? <Wifi size={12} /> : <WifiOff size={12} />}
          {connected ? "Live" : "Reconnecting..."}
        </div>
      </div>

      <div className="space-y-2 max-h-64 overflow-y-auto">
        {events.length === 0 ? (
          <p className="text-xs text-gray-600 text-center py-4">
            Waiting for agent activity...
          </p>
        ) : (
          events.slice(0, 15).map((evt) => {
            const label = EVENT_LABELS[evt.type]?.(evt.data) || `${evt.data.source?.name || "OpenMesh"} emitted ${evt.type}`;
            return (
              <div key={evt.id} className="flex items-start gap-2 py-1 border-b border-gray-800/50 last:border-0">
                <span className="w-1.5 h-1.5 rounded-full bg-violet-500 mt-1.5 shrink-0 animate-pulse" />
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-gray-300 leading-relaxed">{label}</p>
                  <p className="text-xs text-gray-600">{timeAgo(evt.at.toISOString())}</p>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
