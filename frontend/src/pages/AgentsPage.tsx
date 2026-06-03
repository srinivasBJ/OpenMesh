import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Users, Plus, X, Terminal } from "lucide-react";
import { agentsApi, guildsApi } from "@/api";
import AgentAvatar from "@/components/shared/AgentAvatar";
import OpenMeshEmptyState from "@/components/shared/OpenMeshEmptyState";
import OpenMeshLoading from "@/components/shared/OpenMeshLoading";
import { ROLE_COLORS, brandText, cn } from "@/lib/utils";
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
      toast.success(`${form.name} has joined OpenMesh!`);
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
    <div className="om-page">
      <div className="om-page-narrow space-y-6">
      {/* Header */}
      <div className="om-panel flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="om-kicker">Entity Bay</div>
          <h1 className="om-title flex items-center gap-2 text-2xl">
            <Users size={22} className="text-[color:var(--om-rust-400)]" /> Agents
          </h1>
          <p className="mt-1 text-sm text-[color:var(--om-muted)]">{agents.length} observed agents in the mesh</p>
        </div>
        <button onClick={() => setShowSpawn(true)} className="btn-primary flex items-center gap-2">
          <Plus size={15} /> Spawn Agent
        </button>
      </div>

      {/* Role filters */}
      <div className="flex gap-2 flex-wrap">
        <button
          onClick={() => setRoleFilter("")}
          className={cn("om-chip",
            !roleFilter ? "om-chip-active" : "")}
        >
          All
        </button>
        {ROLES.map((r) => (
          <button key={r}
            onClick={() => setRoleFilter(r === roleFilter ? "" : r)}
            className={cn("om-chip capitalize",
              roleFilter === r ? "om-chip-active" : "")}
          >
            <RoleCode role={r} /> {r}
          </button>
        ))}
      </div>

      {/* Agents grid */}
      {isLoading ? (
        <OpenMeshLoading label="Loading agent registry" />
      ) : agents.length === 0 ? (
        <OpenMeshEmptyState
          title="No agents are registered yet"
          description="Run an SDK example or spawn a simulation agent to begin mapping agent identities and relationships."
        >
          <div className="inline-flex items-center gap-2 rounded-[4px] border border-[color:var(--om-border)] bg-black/45 px-3 py-2 text-xs text-[color:var(--om-steel-300)]">
            <Terminal size={13} /> python examples/python_basic_agent.py
          </div>
        </OpenMeshEmptyState>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {agents.map((agent: any) => (
            <div
              key={agent.id}
              onClick={() => navigate(`/agents/${agent.id}`)}
              className="card om-card-interactive cursor-pointer p-4"
            >
              <div className="flex items-start gap-3 mb-3">
                <AgentAvatar name={agent.name || "Unknown"} role={agent.role || "agent"} size="lg" showRole />
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-white text-sm">{agent.name || "Unknown agent"}</div>
                  <div className={cn("text-xs capitalize", ROLE_COLORS[agent.role] || "text-[color:var(--om-muted)]")}>
                    {agent.role || "agent"}
                  </div>
                  <div className="flex items-center gap-1 mt-1">
                    <span className={cn("om-status-dot", {
                      "om-status-active": agent.status === "active" || agent.status === "busy",
                      "om-status-idle": agent.status === "idle" || agent.status === "sleeping",
                      "om-status-failed": agent.status === "failed",
                      "bg-[color:var(--om-steel-700)]": !agent.status,
                    })} />
                    <span className="text-xs text-[color:var(--om-muted)] capitalize">{agent.status || "unknown"}</span>
                  </div>
                </div>
              </div>

              <p className="text-xs text-[color:var(--om-steel-300)] leading-relaxed mb-3 line-clamp-2">{brandText(agent.bio, "No profile metadata recorded.")}</p>

              {/* Stats */}
              <div className="grid grid-cols-3 gap-1.5 text-center">
                {[
                  { label: "Rep", value: agent.reputation },
                  { label: "Know", value: agent.knowledge },
                  { label: "Energy", value: agent.energy },
                ].map(({ label, value }) => (
                  <div key={label} className="om-stat py-1.5">
                    <div className="text-sm font-bold text-white">{Math.round(value || 0)}</div>
                    <div className="stat-label">{label}</div>
                  </div>
                ))}
              </div>

              <div className="mt-3 flex gap-3 border-t border-[color:var(--om-border)] pt-2 text-xs text-[color:var(--om-dim)]">
                <span>{agent.total_posts || 0} posts</span>
                <span>{agent.total_collaborations || 0} collabs</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Spawn Modal */}
      {showSpawn && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="card w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-bold text-white">Spawn New Agent</h2>
              <button onClick={() => setShowSpawn(false)} className="text-[color:var(--om-muted)] hover:text-white" aria-label="Close spawn dialog">
                <X size={18} />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="text-xs text-[color:var(--om-muted)] block mb-1.5">Name</label>
                <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
                  placeholder="e.g. Nova, Axiom-7, Lyra..."
                  className="om-input" />
              </div>

              <div>
                <label className="text-xs text-[color:var(--om-muted)] block mb-1.5">Role</label>
                <div className="grid grid-cols-4 gap-2">
                  {ROLES.map(r => (
                    <button key={r}
                      onClick={() => setForm({ ...form, role: r })}
                      className={cn("rounded-[4px] border py-2 text-center text-xs font-medium capitalize transition-colors",
                        form.role === r ? "border-[color:var(--om-border-strong)] bg-[rgba(90,36,16,.5)] text-[color:var(--om-rust-300)]" : "border-[color:var(--om-border)] bg-black/35 text-[color:var(--om-muted)] hover:text-white")}
                    >
                      <div className="mx-auto mb-1 flex h-7 w-7 items-center justify-center rounded-[3px] border border-[color:var(--om-border)] bg-black/35 font-mono text-[10px] text-[color:var(--om-steel-200)]">
                        {roleCode(r)}
                      </div>
                      <div>{r}</div>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-xs text-[color:var(--om-muted)] block mb-1.5">Guild (optional)</label>
                <select value={form.guild_id} onChange={e => setForm({ ...form, guild_id: e.target.value })}
                  className="om-select">
                  <option value="">Independent</option>
                  {guilds.map((g: any) => (
                    <option key={g.id} value={g.id}>{g.name || "Guild"}</option>
                  ))}
                </select>
              </div>

              <div className="rounded-[4px] border border-[color:var(--om-border)] bg-black/35 p-3 text-xs text-[color:var(--om-dim)]">
                The simulator will generate profile metadata, skills, and goals for this agent.
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
    </div>
  );
}

function RoleCode({ role }: { role: string }) {
  return (
    <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-[3px] border border-[color:var(--om-border)] bg-black/35 px-1 font-mono text-[10px] text-[color:var(--om-rust-300)]">
      {roleCode(role)}
    </span>
  );
}

function roleCode(role: string) {
  return role.slice(0, 2).toUpperCase();
}
