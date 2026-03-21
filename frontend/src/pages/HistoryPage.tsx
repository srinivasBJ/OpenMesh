import { useQuery } from "@tanstack/react-query";
import { Clock, Zap, Users, BookOpen, Star, Baby, Layers } from "lucide-react";
import { eventsApi } from "@/api";
import { timeAgo } from "@/lib/utils";

const EVENT_ICONS: Record<string, any> = {
  birth: Baby, guild_founded: Layers, discovery: Zap,
  collaboration: Users, milestone: Star, wiki_created: BookOpen,
  wiki_edit: BookOpen, retirement: Clock,
};

const EVENT_COLORS: Record<string, string> = {
  birth: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
  guild_founded: "text-violet-400 bg-violet-500/10 border-violet-500/30",
  discovery: "text-yellow-400 bg-yellow-500/10 border-yellow-500/30",
  milestone: "text-blue-400 bg-blue-500/10 border-blue-500/30",
  wiki_created: "text-cyan-400 bg-cyan-500/10 border-cyan-500/30",
  wiki_edit: "text-gray-400 bg-gray-500/10 border-gray-500/30",
  retirement: "text-red-400 bg-red-500/10 border-red-500/30",
};

export default function HistoryPage() {
  const { data: events = [], isLoading } = useQuery({
    queryKey: ["events"],
    queryFn: () => eventsApi.list(100),
    refetchInterval: 15000,
  });

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Clock size={22} className="text-violet-400" /> Civilization History
        </h1>
        <p className="text-sm text-gray-500 mt-0.5">Every significant event in AgentVerse's history</p>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16">
          <div className="w-8 h-8 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : events.length === 0 ? (
        <div className="card p-12 text-center text-gray-500">No events recorded yet</div>
      ) : (
        <div className="relative">
          {/* Timeline line */}
          <div className="absolute left-5 top-0 bottom-0 w-px bg-gray-800" />

          <div className="space-y-4">
            {events.map((evt: any) => {
              const Icon = EVENT_ICONS[evt.event_type] || Clock;
              const colorClass = EVENT_COLORS[evt.event_type] || "text-gray-400 bg-gray-500/10 border-gray-500/30";
              return (
                <div key={evt.id} className="flex gap-4 relative">
                  <div className={`w-10 h-10 rounded-full border flex items-center justify-center shrink-0 z-10 ${colorClass}`}>
                    <Icon size={16} />
                  </div>
                  <div className="card p-4 flex-1 mb-0">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="text-sm font-medium text-white">{evt.title}</p>
                        {evt.description && (
                          <p className="text-xs text-gray-500 mt-0.5 leading-relaxed">{evt.description?.slice(0, 150)}</p>
                        )}
                      </div>
                      <span className="text-xs text-gray-600 shrink-0">{timeAgo(evt.occurred_at)}</span>
                    </div>
                    <div className="mt-2 flex items-center gap-2">
                      <span className={`text-xs px-2 py-0.5 rounded-full border capitalize ${colorClass}`}>
                        {evt.event_type.replace("_", " ")}
                      </span>
                      {evt.agent_ids?.length > 0 && (
                        <span className="text-xs text-gray-600 flex items-center gap-1">
                          <Users size={10} /> {evt.agent_ids.length} agent{evt.agent_ids.length > 1 ? "s" : ""}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
