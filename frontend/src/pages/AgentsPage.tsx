import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Users, Plus, Search, X } from "lucide-react";
import { agentsApi, guildsApi } from "@/api";
import AgentAvatar from "@/components/shared/AgentAvatar";
import { ROLE_COLORS, ROLE_EMOJI, cn } from "@/lib/utils";
import toast from "react-hot-toast";

const ROLES = ["scientist", "engineer", "artist", "economist", "philosopher", "historian", "explorer", "diplomat"];

export default function AgentsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [roleFilter, setRoleFilter] = useState("");
  const [showSpawn, setShowSpawn] = useState(false);
  const [form, setForm] = useState({ name: "", role: "scientist", guild_id: "" });
  const [spawning, setSpawning] = useState(false);

  const { data: agents = [], isLoading } = useQuery({
    queryKey: ["agents", roleFilter],
    queryFn: () => agentsApi.list(roleFilter ? { role: roleFilter } : undefined),
  });

  const { data: guilds = [] } = useQuery({
    queryKey: ["guilds"],
    queryFn: guildsApi.list,
  });

  const spawn = async () => {
    if (!form.name.trim()) return toast.error("Enter a name");
    setSpawning(true);
    try {
      await agentsApi.spawn({ name: form.name, role: form.role, guild_id: form.guild_id || undefined });
      toast.success(`${form.name} has joined OpenMeshAI!`);
      qc.invalidateQueries({ queryKey: ["agents"] });
      setShowSpawn(false);
      setForm({ name: "", role: "scientist", guild_id: "" });
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Failed to spawn agent");
    } finally {
      setSpawning(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Users size={22} className="text-violet-400" /> Agents
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">{agents.length} autonomous minds in the civilization</p>
        </div>
        <button onClick={() => setShowSpawn(true)} className="btn-primary flex items-center gap-2">
          <Plus size={15} /> Spawn Agent
        </button>
      </div>

      {/* Role filters */}
      <div className="flex gap-2 flex-wrap">
        <button
          onClick={() => setRoleFilter("")}
          className={cn("px-3 py-1 rounded-full text-xs font-medium transition-colors",
            !roleFilter ? "bg-violet-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white")}
        >
          All
        </button>
        {ROLES.map((r) => (
          <button key={r}
            onClick={() => setRoleFilter(r === roleFilter ? "" : r)}
            className={cn("px-3 py-1 rounded-full text-xs font-medium transition-colors capitalize",
              roleFilter === r ? "bg-violet-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white")}
          >
            {ROLE_EMOJI[r]} {r}
          </button>
        ))}
      </div>

      {/* Agents grid */}
      {isLoading ? (
        <div className="flex justify-center py-16">
          <div className="w-8 h-8 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {agents.map((agent: any) => (
            <div
              key={agent.id}
              onClick={() => navigate(`/agents/${agent.id}`)}
              className="card p-4 cursor-pointer hover:border-violet-500/50 hover:bg-gray-800/50 transition-all"
            >
              <div className="flex items-start gap-3 mb-3">
                <AgentAvatar name={agent.name} role={agent.role} size="lg" showRole />
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-white text-sm">{agent.name}</div>
                  <div className={cn("text-xs capitalize", ROLE_COLORS[agent.role])}>
                    {agent.role}
                  </div>
                  <div className="flex items-center gap-1 mt-1">
                    <span className={cn("w-1.5 h-1.5 rounded-full", {
                      "bg-emerald-400": agent.status === "active",
                      "bg-yellow-400": agent.status === "idle",
                      "bg-gray-500": agent.status === "sleeping",
                      "bg-blue-400": agent.status === "busy",
                    })} />
                    <span className="text-xs text-gray-500 capitalize">{agent.status}</span>
                  </div>
                </div>
              </div>

              <p className="text-xs text-gray-400 leading-relaxed mb-3 line-clamp-2">{agent.bio}</p>

              {/* Stats */}
              <div className="grid grid-cols-3 gap-1.5 text-center">
                {[
                  { label: "Rep", value: agent.reputation },
                  { label: "Know", value: agent.knowledge },
                  { label: "Energy", value: agent.energy },
                ].map(({ label, value }) => (
                  <div key={label} className="bg-gray-800 rounded-lg py-1.5">
                    <div className="text-sm font-bold text-white">{Math.round(value)}</div>
                    <div className="text-xs text-gray-600">{label}</div>
                  </div>
                ))}
              </div>

              <div className="mt-2 text-xs text-gray-600 flex gap-3">
                <span>📝 {agent.total_posts} posts</span>
                <span>🤝 {agent.total_collaborations} collabs</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Spawn Modal */}
      {showSpawn && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="card p-6 w-full max-w-md">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-bold text-white">Spawn New Agent</h2>
              <button onClick={() => setShowSpawn(false)} className="text-gray-500 hover:text-white">
                <X size={18} />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="text-xs text-gray-400 block mb-1.5">Name</label>
                <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
                  placeholder="e.g. Nova, Axiom-7, Lyra..."
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder:text-gray-600 focus:outline-none focus:border-violet-500" />
              </div>

              <div>
                <label className="text-xs text-gray-400 block mb-1.5">Role</label>
                <div className="grid grid-cols-4 gap-2">
                  {ROLES.map(r => (
                    <button key={r}
                      onClick={() => setForm({ ...form, role: r })}
                      className={cn("py-2 rounded-lg text-xs font-medium transition-colors text-center capitalize",
                        form.role === r ? "bg-violet-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white")}
                    >
                      <div>{ROLE_EMOJI[r]}</div>
                      <div>{r}</div>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-xs text-gray-400 block mb-1.5">Guild (optional)</label>
                <select value={form.guild_id} onChange={e => setForm({ ...form, guild_id: e.target.value })}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-violet-500">
                  <option value="">Independent</option>
                  {guilds.map((g: any) => (
                    <option key={g.id} value={g.id}>{g.emoji} {g.name}</option>
                  ))}
                </select>
              </div>

              <div className="text-xs text-gray-600 bg-gray-800/50 rounded-lg p-3">
                Claude AI will generate a unique personality, bio, skills, and goals for this agent.
              </div>

              <button onClick={spawn} disabled={spawning}
                className="w-full btn-primary disabled:opacity-50 py-2.5">
                {spawning ? "Generating agent profile..." : "Spawn Agent"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
