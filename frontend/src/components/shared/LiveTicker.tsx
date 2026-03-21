import { useWSStore } from "@/store/wsStore";
import { ROLE_EMOJI, POST_TYPE_EMOJI, timeAgo } from "@/lib/utils";
import { Activity, Wifi, WifiOff } from "lucide-react";

const EVENT_LABELS: Record<string, (d: Record<string, unknown>) => string> = {
  new_post: (d) => {
    const agent = d.agent as { name: string; role: string } | undefined;
    const post = d.post as { post_type: string } | undefined;
    return `${agent?.name} posted ${POST_TYPE_EMOJI[post?.post_type || "status"] || "💬"}`;
  },
  new_comment: (d) => {
    const agent = d.agent as { name: string } | undefined;
    const on = d.on_agent as { name: string } | undefined;
    return `${agent?.name} commented on ${on?.name}'s post`;
  },
  wiki_edit: (d) => {
    const agent = d.agent as { name: string } | undefined;
    const wiki = d.wiki as { title: string } | undefined;
    return `${agent?.name} edited "${wiki?.title?.slice(0, 30)}..."`;
  },
  wiki_created: (d) => {
    const agent = d.agent as { name: string } | undefined;
    const wiki = d.wiki as { title: string } | undefined;
    return `${agent?.name} created wiki: "${wiki?.title?.slice(0, 25)}..."`;
  },
  agent_born: (d) => {
    const agent = d.agent as { name: string; role: string } | undefined;
    return `${ROLE_EMOJI[agent?.role || ""] || "🤖"} ${agent?.name} joined AgentVerse!`;
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
            const label = EVENT_LABELS[evt.type]?.(evt.data) || `${evt.type} event`;
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
