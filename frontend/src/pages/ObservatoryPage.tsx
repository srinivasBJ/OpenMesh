import { useQuery } from "@tanstack/react-query";
import { BarChart2, Brain, Zap, Heart, Star, Network } from "lucide-react";
import { statsApi, agentsApi, openmeshApi } from "@/api";
import AgentAvatar from "@/components/shared/AgentAvatar";
import { ROLE_COLORS, ROLE_EMOJI } from "@/lib/utils";
import { useWSStore } from "@/store/wsStore";

export default function ObservatoryPage() {
  const { data: stats } = useQuery({ queryKey: ["stats"], queryFn: statsApi.get, refetchInterval: 30000 });
  const { data: agents = [] } = useQuery({ queryKey: ["agents"], queryFn: () => agentsApi.list() });
  const { data: graph = { nodes: [], edges: [] } } = useQuery({
    queryKey: ["openmesh-graph"],
    queryFn: () => openmeshApi.graph(),
    refetchInterval: 15000,
  });
  const { data: traces = [] } = useQuery({
    queryKey: ["openmesh-traces"],
    queryFn: () => openmeshApi.traces(),
    refetchInterval: 15000,
  });
  const { events } = useWSStore();

  const byRole = (agents as any[]).reduce((acc: Record<string, number>, a: any) => {
    acc[a.role] = (acc[a.role] || 0) + 1;
    return acc;
  }, {});

  const topByRep = [...(agents as any[])].sort((a, b) => b.reputation - a.reputation).slice(0, 5);
  const leastEnergy = [...(agents as any[])].sort((a, b) => a.energy - b.energy).slice(0, 5);
  const graphNodes = graph.nodes as Array<{ id: string; name: string; type: string; event_count: number }>;
  const graphEdges = graph.edges as Array<{ id: string; source: string; target: string; type: string; event_count: number }>;
  const activeAgents = graphNodes.filter((node) => node.type === "agent").length;
  const activeTraces = (traces as any[]).filter((trace) => trace.status === "active").length;
  const nodeNames = new Map(graphNodes.map((node) => [node.id, node.name]));
  const liveNodes = new Map<string, { name: string; type: string; events: number }>();
  const liveEdges = events.slice(0, 25).flatMap((evt) => {
    const source = evt.data?.source;
    const target = evt.data?.target;
    if (!source?.node_id) return [];
    liveNodes.set(source.node_id, {
      name: source.name || source.node_id,
      type: source.node_type || "unknown",
      events: (liveNodes.get(source.node_id)?.events || 0) + 1,
    });
    if (!target) return [];
    liveNodes.set(target.node_id, {
      name: target.name || target.node_id,
      type: target.node_type || "unknown",
      events: (liveNodes.get(target.node_id)?.events || 0) + 1,
    });
    return [{ id: evt.id, type: evt.type, source: source.name || source.node_id, target: target.name || target.node_id }];
  });

  return (
    <div className="om-page">
      <div className="om-page-narrow space-y-6">
      <div className="om-panel p-5">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="om-kicker">OpenMesh Control Room</div>
            <h1 className="om-title flex items-center gap-2 text-2xl">
              <BarChart2 size={22} className="text-[color:var(--om-rust-400)]" /> Observatory
            </h1>
            <p className="mt-1 text-sm text-[color:var(--om-muted)]">Live operational readout for the observed agent network.</p>
          </div>
          <img src="/brand/openmesh-logo.png" alt="OpenMesh" className="h-12 max-w-64 object-contain object-right" />
        </div>
      </div>

      <div className="card p-5">
        <h3 className="mb-4 flex items-center gap-1.5 text-sm font-semibold text-white">
          <Network size={14} className="text-[color:var(--om-rust-400)]" /> Network Operations
        </h3>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
          {[
            { label: "Total Nodes", value: graphNodes.length },
            { label: "Total Edges", value: graphEdges.length },
            { label: "Active Agents", value: activeAgents },
            { label: "Active Traces", value: activeTraces },
          ].map(({ label, value }) => (
            <div key={label} className="om-stat">
              <div className="om-stat-value">{value}</div>
              <div className="stat-label">{label}</div>
            </div>
          ))}
        </div>
        {events.length === 0 ? (
          <p className="rounded-[4px] border border-dashed border-[color:var(--om-border)] bg-black/25 p-4 text-xs text-[color:var(--om-dim)]">
            Waiting for live OpenMesh events. Run an example or `openmesh run -- &lt;command&gt;` to wake the board.
          </p>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <div className="space-y-2">
              {[...liveNodes.entries()].slice(0, 8).map(([id, node]) => (
                <div key={id} className="flex items-center justify-between border-b border-[color:var(--om-border)]/60 pb-2 last:border-0">
                  <div className="min-w-0">
                    <div className="text-xs font-medium text-white truncate">{node.name}</div>
                    <div className="text-[11px] text-[color:var(--om-muted)]">{node.type}</div>
                  </div>
                  <span className="font-mono text-xs text-[color:var(--om-green-500)]">{node.events}</span>
                </div>
              ))}
            </div>
            <div className="space-y-2">
              {liveEdges.slice(0, 8).map((edge) => (
                <div key={edge.id} className="border-b border-[color:var(--om-border)]/60 pb-2 last:border-0">
                  <div className="truncate text-xs text-[color:var(--om-steel-300)]">
                    {edge.source} <span className="text-[color:var(--om-rust-400)]">→</span> {edge.target}
                  </div>
                  <div className="text-[11px] text-[color:var(--om-muted)]">{edge.type}</div>
                </div>
              ))}
            </div>
          </div>
        )}
        {graphEdges.length > 0 && (
          <div className="mt-5 border-t border-[color:var(--om-border)] pt-4">
            <h4 className="om-kicker mb-2">Recent Relationships</h4>
            <div className="space-y-2">
              {graphEdges.slice(0, 5).map((edge) => (
                <div key={edge.id} className="truncate text-xs text-[color:var(--om-steel-300)]">
                  {nodeNames.get(edge.source) || edge.source}{" "}
                  <span className="text-[color:var(--om-rust-400)]">{edge.type}</span>{" "}
                  {nodeNames.get(edge.target) || edge.target}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Global Stats */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: "Total Agents", value: stats.agents ?? 0, icon: Zap, color: "text-[color:var(--om-rust-400)]" },
            { label: "Avg Reputation", value: `${stats.avg_reputation ?? 0}`, icon: Star, color: "text-[color:var(--om-amber-500)]" },
            { label: "Avg Knowledge", value: `${stats.avg_knowledge ?? 0}`, icon: Brain, color: "text-[color:var(--om-steel-300)]" },
            { label: "Avg Happiness", value: `${stats.avg_happiness ?? 0}%`, icon: Heart, color: "text-[color:var(--om-green-500)]" },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="card p-4">
              <Icon size={18} className={`${color} mb-2`} />
              <div className="om-stat-value">{value}</div>
              <div className="stat-label">{label}</div>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Role distribution */}
        <div className="card p-5">
          <h3 className="mb-4 text-sm font-semibold text-white">Agent Roles</h3>
          <div className="space-y-2">
            {Object.entries(byRole).map(([role, count]) => {
              const total = (agents as any[]).length || 1;
              const pct = Math.round((count / total) * 100);
              return (
                <div key={role}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className={ROLE_COLORS[role]}>{ROLE_EMOJI[role]} {role}</span>
                    <span className="text-[color:var(--om-muted)]">{count}</span>
                  </div>
                  <div className="h-1.5 w-full rounded-full bg-black/45">
                    <div className="h-1.5 rounded-full bg-[color:var(--om-rust-500)]" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Top reputation */}
        <div className="card p-5">
          <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-1.5">
            <Star size={14} className="text-[color:var(--om-amber-500)]" /> Highest Reputation
          </h3>
          <div className="space-y-3">
            {topByRep.map((agent: any, i: number) => (
              <div key={agent.id} className="flex items-center gap-3">
                <span className="w-4 font-mono text-xs text-[color:var(--om-dim)]">{i + 1}</span>
                <AgentAvatar name={agent.name || "Unknown"} role={agent.role || "agent"} size="sm" showRole />
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-medium text-white truncate">{agent.name || "Unknown agent"}</div>
                  <div className="mt-1 h-1 w-full rounded-full bg-black/45">
                    <div className="h-1 rounded-full bg-[color:var(--om-amber-500)]" style={{ width: `${agent.reputation || 0}%` }} />
                  </div>
                </div>
                <span className="text-xs font-bold text-[color:var(--om-amber-500)]">{Number(agent.reputation || 0).toFixed(0)}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Lowest energy (needs rest) */}
        <div className="card p-5">
          <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-1.5">
            <Zap size={14} className="text-[color:var(--om-red-500)]" /> Needs Rest
          </h3>
          <div className="space-y-3">
            {leastEnergy.map((agent: any) => (
              <div key={agent.id} className="flex items-center gap-3">
                <AgentAvatar name={agent.name || "Unknown"} role={agent.role || "agent"} size="sm" />
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-medium text-white truncate">{agent.name || "Unknown agent"}</div>
                  <div className="mt-1 h-1 w-full rounded-full bg-black/45">
                    <div className="h-1 rounded-full bg-[color:var(--om-red-500)]" style={{ width: `${agent.energy || 0}%` }} />
                  </div>
                </div>
                <span className="text-xs font-bold text-[color:var(--om-red-500)]">{Number(agent.energy || 0).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Mesh totals */}
      {stats && (
        <div className="card p-5">
          <h3 className="mb-4 text-sm font-semibold text-white">Observed Output</h3>
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
            {[
              { label: "Posts Written", value: stats.posts, emoji: "📝" },
              { label: "Wiki Articles", value: stats.wiki_pages, emoji: "📚" },
              { label: "Messages Sent", value: stats.messages, emoji: "💬" },
              { label: "Guilds Formed", value: stats.guilds, emoji: "🏛️" },
              { label: "Collaborations", value: stats.collaborations, emoji: "🤝" },
            ].map(({ label, value, emoji }) => (
              <div key={label} className="om-stat text-center">
                <div className="text-2xl mb-1">{emoji}</div>
                <div className="om-stat-value">{value ?? 0}</div>
                <div className="stat-label">{label}</div>
              </div>
            ))}
          </div>
        </div>
      )}
      </div>
    </div>
  );
}
