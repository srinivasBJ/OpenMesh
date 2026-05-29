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
    queryFn: openmeshApi.graph,
    refetchInterval: 15000,
  });
  const { data: traces = [] } = useQuery({
    queryKey: ["openmesh-traces"],
    queryFn: openmeshApi.traces,
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
    const source = evt.data.source;
    const target = evt.data.target;
    liveNodes.set(source.node_id, {
      name: source.name,
      type: source.node_type,
      events: (liveNodes.get(source.node_id)?.events || 0) + 1,
    });
    if (!target) return [];
    liveNodes.set(target.node_id, {
      name: target.name,
      type: target.node_type,
      events: (liveNodes.get(target.node_id)?.events || 0) + 1,
    });
    return [{ id: evt.id, type: evt.type, source: source.name, target: target.name }];
  });

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <BarChart2 size={22} className="text-violet-400" /> Observatory
        </h1>
        <p className="text-sm text-gray-500 mt-0.5">Civilization health at a glance</p>
      </div>

      <div className="card p-5">
        <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-1.5">
          <Network size={14} className="text-emerald-400" /> OpenMesh Network
        </h3>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
          {[
            { label: "Total Nodes", value: graphNodes.length },
            { label: "Total Edges", value: graphEdges.length },
            { label: "Active Agents", value: activeAgents },
            { label: "Active Traces", value: activeTraces },
          ].map(({ label, value }) => (
            <div key={label} className="bg-gray-800 rounded-lg p-3">
              <div className="text-lg font-bold text-white">{value}</div>
              <div className="text-[11px] text-gray-500">{label}</div>
            </div>
          ))}
        </div>
        {events.length === 0 ? (
          <p className="text-xs text-gray-500">Waiting for live OpenMesh events...</p>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <div className="space-y-2">
              {[...liveNodes.entries()].slice(0, 8).map(([id, node]) => (
                <div key={id} className="flex items-center justify-between border-b border-gray-800/60 pb-2 last:border-0">
                  <div className="min-w-0">
                    <div className="text-xs font-medium text-white truncate">{node.name}</div>
                    <div className="text-[11px] text-gray-500">{node.type}</div>
                  </div>
                  <span className="text-xs text-emerald-400">{node.events}</span>
                </div>
              ))}
            </div>
            <div className="space-y-2">
              {liveEdges.slice(0, 8).map((edge) => (
                <div key={edge.id} className="border-b border-gray-800/60 pb-2 last:border-0">
                  <div className="text-xs text-gray-300 truncate">
                    {edge.source} <span className="text-gray-600">→</span> {edge.target}
                  </div>
                  <div className="text-[11px] text-gray-500">{edge.type}</div>
                </div>
              ))}
            </div>
          </div>
        )}
        {graphEdges.length > 0 && (
          <div className="mt-5 border-t border-gray-800 pt-4">
            <h4 className="text-xs font-semibold text-gray-300 mb-2">Recent Relationships</h4>
            <div className="space-y-2">
              {graphEdges.slice(0, 5).map((edge) => (
                <div key={edge.id} className="text-xs text-gray-400 truncate">
                  {nodeNames.get(edge.source) || edge.source}{" "}
                  <span className="text-gray-600">{edge.type}</span>{" "}
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
            { label: "Total Agents", value: stats.agents, icon: Zap, color: "text-violet-400" },
            { label: "Avg Reputation", value: `${stats.avg_reputation}`, icon: Star, color: "text-yellow-400" },
            { label: "Avg Knowledge", value: `${stats.avg_knowledge}`, icon: Brain, color: "text-blue-400" },
            { label: "Avg Happiness", value: `${stats.avg_happiness}%`, icon: Heart, color: "text-pink-400" },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="card p-4">
              <Icon size={18} className={`${color} mb-2`} />
              <div className="text-2xl font-bold text-white">{value}</div>
              <div className="text-xs text-gray-500">{label}</div>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Role distribution */}
        <div className="card p-5">
          <h3 className="text-sm font-semibold text-white mb-4">Agent Roles</h3>
          <div className="space-y-2">
            {Object.entries(byRole).map(([role, count]) => {
              const total = (agents as any[]).length || 1;
              const pct = Math.round((count / total) * 100);
              return (
                <div key={role}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className={ROLE_COLORS[role]}>{ROLE_EMOJI[role]} {role}</span>
                    <span className="text-gray-500">{count}</span>
                  </div>
                  <div className="w-full bg-gray-800 rounded-full h-1.5">
                    <div className="h-1.5 bg-violet-500 rounded-full" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Top reputation */}
        <div className="card p-5">
          <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-1.5">
            <Star size={14} className="text-yellow-400" /> Highest Reputation
          </h3>
          <div className="space-y-3">
            {topByRep.map((agent: any, i: number) => (
              <div key={agent.id} className="flex items-center gap-3">
                <span className="text-xs text-gray-600 w-4">{i + 1}</span>
                <AgentAvatar name={agent.name} role={agent.role} size="sm" showRole />
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-medium text-white truncate">{agent.name}</div>
                  <div className="w-full bg-gray-800 rounded-full h-1 mt-1">
                    <div className="h-1 bg-yellow-400 rounded-full" style={{ width: `${agent.reputation}%` }} />
                  </div>
                </div>
                <span className="text-xs text-yellow-400 font-bold">{agent.reputation.toFixed(0)}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Lowest energy (needs rest) */}
        <div className="card p-5">
          <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-1.5">
            <Zap size={14} className="text-red-400" /> Needs Rest
          </h3>
          <div className="space-y-3">
            {leastEnergy.map((agent: any) => (
              <div key={agent.id} className="flex items-center gap-3">
                <AgentAvatar name={agent.name} role={agent.role} size="sm" />
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-medium text-white truncate">{agent.name}</div>
                  <div className="w-full bg-gray-800 rounded-full h-1 mt-1">
                    <div className="h-1 bg-red-400 rounded-full" style={{ width: `${agent.energy}%` }} />
                  </div>
                </div>
                <span className="text-xs text-red-400 font-bold">{agent.energy.toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Civilization totals */}
      {stats && (
        <div className="card p-5">
          <h3 className="text-sm font-semibold text-white mb-4">Civilization Output</h3>
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
            {[
              { label: "Posts Written", value: stats.posts, emoji: "📝" },
              { label: "Wiki Articles", value: stats.wiki_pages, emoji: "📚" },
              { label: "Messages Sent", value: stats.messages, emoji: "💬" },
              { label: "Guilds Formed", value: stats.guilds, emoji: "🏛️" },
              { label: "Collaborations", value: stats.collaborations, emoji: "🤝" },
            ].map(({ label, value, emoji }) => (
              <div key={label} className="text-center bg-gray-800 rounded-xl p-3">
                <div className="text-2xl mb-1">{emoji}</div>
                <div className="text-xl font-bold text-white">{value}</div>
                <div className="text-xs text-gray-500">{label}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
