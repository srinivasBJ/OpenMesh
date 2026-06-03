import { useQuery } from "@tanstack/react-query";
import { Clock, Zap, Users, BookOpen, Star, Baby, Layers } from "lucide-react";
import { eventsApi } from "@/api";
import OpenMeshEmptyState from "@/components/shared/OpenMeshEmptyState";
import OpenMeshLoading from "@/components/shared/OpenMeshLoading";
import { brandText, timeAgo } from "@/lib/utils";

const EVENT_ICONS: Record<string, any> = {
  birth: Baby, guild_founded: Layers, discovery: Zap,
  collaboration: Users, milestone: Star, wiki_created: BookOpen,
  wiki_edit: BookOpen, retirement: Clock,
};

const EVENT_COLORS: Record<string, string> = {
  birth: "text-[color:var(--om-green-500)] bg-black/40 border-[color:var(--om-green-500)]/40",
  guild_founded: "text-[color:var(--om-rust-300)] bg-black/40 border-[color:var(--om-rust-500)]/40",
  discovery: "text-[color:var(--om-amber-500)] bg-black/40 border-[color:var(--om-amber-500)]/40",
  milestone: "text-[color:var(--om-steel-300)] bg-black/40 border-[color:var(--om-steel-500)]/40",
  wiki_created: "text-[color:var(--om-oxide-600)] bg-black/40 border-[color:var(--om-oxide-600)]/40",
  wiki_edit: "text-[color:var(--om-muted)] bg-black/40 border-[color:var(--om-border)]",
  retirement: "text-[color:var(--om-red-500)] bg-black/40 border-[color:var(--om-red-500)]/40",
};

export default function HistoryPage() {
  const { data: events = [], isLoading } = useQuery({
    queryKey: ["events"],
    queryFn: () => eventsApi.list(100),
    refetchInterval: 15000,
  });

  return (
    <div className="om-page">
      <div className="om-page-compact space-y-6">
      <div className="om-panel p-5">
        <div className="om-kicker">Historical Recorder</div>
        <h1 className="om-title flex items-center gap-2 text-2xl">
          <Clock size={22} className="text-[color:var(--om-rust-400)]" /> History
        </h1>
        <p className="mt-1 text-sm text-[color:var(--om-muted)]">Chronological operational history from simulation and OpenMesh events.</p>
      </div>

      {isLoading ? (
        <OpenMeshLoading label="Loading history ledger" />
      ) : events.length === 0 ? (
        <OpenMeshEmptyState
          title="No historical events recorded"
          description="History will populate as OpenMesh observes agents, workflows, and generated artifacts."
        />
      ) : (
        <div className="relative">
          {/* Timeline line */}
          <div className="absolute left-5 top-0 bottom-0 w-px bg-[color:var(--om-border)]" />

          <div className="space-y-4">
            {events.map((evt: any) => {
              const Icon = EVENT_ICONS[evt.event_type] || Clock;
              const colorClass = EVENT_COLORS[evt.event_type] || "text-gray-400 bg-gray-500/10 border-gray-500/30";
              return (
                <div key={evt.id} className="flex gap-4 relative">
                  <div className={`z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-[6px] border ${colorClass}`}>
                    <Icon size={16} />
                  </div>
                  <div className="card p-4 flex-1 mb-0">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="text-sm font-medium text-white">{brandText(evt.title || evt.event_type, "Recorded event")}</p>
                        {evt.description && (
                          <p className="text-xs text-[color:var(--om-muted)] mt-0.5 leading-relaxed">{brandText(evt.description).slice(0, 150)}</p>
                        )}
                      </div>
                      <span className="text-xs text-[color:var(--om-dim)] shrink-0">{evt.occurred_at ? timeAgo(evt.occurred_at) : "time unknown"}</span>
                    </div>
                    <div className="mt-2 flex items-center gap-2">
                      <span className={`rounded-full border px-2 py-0.5 text-xs capitalize ${colorClass}`}>
                        {String(evt.event_type || "event").replace("_", " ")}
                      </span>
                      {evt.agent_ids?.length > 0 && (
                        <span className="flex items-center gap-1 text-xs text-[color:var(--om-dim)]">
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
    </div>
  );
}
