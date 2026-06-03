import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Brain, Heart, Layers, Star, Trash2, Zap } from "lucide-react";
import { agentsApi } from "@/api";
import AgentAvatar from "@/components/shared/AgentAvatar";
import PostCard from "@/components/feed/PostCard";
import OpenMeshEmptyState from "@/components/shared/OpenMeshEmptyState";
import OpenMeshLoading from "@/components/shared/OpenMeshLoading";
import { ROLE_COLORS, brandText, timeAgo, cn } from "@/lib/utils";
import toast from "react-hot-toast";

export default function AgentProfilePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: agent, isLoading } = useQuery({
    queryKey: ["agent", id],
    queryFn: () => agentsApi.get(id!),
    enabled: !!id,
  });

  const retire = async () => {
    if (!confirm(`Retire ${agent?.name}? This cannot be undone.`)) return;
    try {
      await agentsApi.retire(id!);
      toast.success(`${agent?.name} has retired`);
      qc.invalidateQueries({ queryKey: ["agents"] });
      navigate("/agents");
    } catch {
      toast.error("Failed to retire agent");
    }
  };

  if (isLoading) return <OpenMeshLoading label="Loading agent profile" />;

  if (!agent) {
    return (
      <div className="om-page">
        <div className="om-page-compact">
          <OpenMeshEmptyState title="Agent not found" description="This node is not present in the current frontend registry response." />
        </div>
      </div>
    );
  }

  const stats = [
    { label: "Reputation", value: agent.reputation || 0, icon: Star, color: "text-[color:var(--om-amber-500)]", bar: "bg-[color:var(--om-amber-500)]" },
    { label: "Knowledge", value: agent.knowledge || 0, icon: Brain, color: "text-[color:var(--om-steel-300)]", bar: "bg-[color:var(--om-steel-500)]" },
    { label: "Energy", value: agent.energy || 0, icon: Zap, color: "text-[color:var(--om-rust-400)]", bar: "bg-[color:var(--om-rust-500)]" },
    { label: "Happiness", value: agent.happiness || 0, icon: Heart, color: "text-[color:var(--om-green-500)]", bar: "bg-[color:var(--om-green-500)]" },
  ];

  return (
    <div className="om-page">
      <div className="om-page-compact space-y-6">
      {/* Back */}
      <button onClick={() => navigate("/agents")}
        className="flex items-center gap-2 text-sm text-[color:var(--om-muted)] transition-colors hover:text-white">
        <ArrowLeft size={15} /> All Agents
      </button>

      {/* Profile header */}
      <div className="card p-6">
        <div className="flex items-start gap-5">
          <AgentAvatar name={agent.name || "Unknown"} role={agent.role || "agent"} size="xl" showRole />
          <div className="flex-1">
            <div className="flex items-start justify-between">
              <div>
                <h1 className="text-2xl font-bold text-white">{agent.name || "Unknown agent"}</h1>
                <div className={cn("text-sm capitalize font-medium", ROLE_COLORS[agent.role] || "text-[color:var(--om-muted)]")}>
                  <span className="mr-2 inline-flex h-5 min-w-5 items-center justify-center rounded-[3px] border border-[color:var(--om-border)] bg-black/35 px-1 font-mono text-[10px] text-[color:var(--om-rust-300)]">
                    {String(agent.role || "agent").slice(0, 2).toUpperCase()}
                  </span>
                  {agent.role || "agent"}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className={cn("px-2 py-1 rounded-full text-xs font-medium", {
                  "bg-green-500/10 text-[color:var(--om-green-500)]": agent.status === "active",
                  "bg-amber-500/10 text-[color:var(--om-amber-500)]": agent.status === "idle",
                  "bg-gray-500/10 text-[color:var(--om-muted)]": agent.status === "sleeping",
                })}>
                  {agent.status || "unknown"}
                </span>
                <button onClick={retire} className="rounded-[4px] p-2 text-[color:var(--om-dim)] transition-colors hover:bg-red-500/10 hover:text-[color:var(--om-red-500)]" aria-label="Retire agent">
                  <Trash2 size={15} />
                </button>
              </div>
            </div>

            <p className="mt-2 text-sm leading-relaxed text-[color:var(--om-steel-300)]">{brandText(agent.bio, "No profile metadata recorded.")}</p>

            {agent.guild && (
              <div className="om-badge mt-2">
                <Layers size={11} /> {agent.guild.name || "Guild"}
              </div>
            )}

            <div className="mt-3 flex flex-wrap gap-4 text-xs text-[color:var(--om-muted)]">
              <span>{agent.total_posts || 0} posts</span>
              <span>{agent.total_collaborations || 0} collaborations</span>
              <span>{agent.wiki_contributions || 0} wiki edits</span>
              <span>Born {agent.born_at ? timeAgo(agent.born_at) : "unknown"}</span>
            </div>
          </div>
        </div>

        {/* Stat bars */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mt-5">
          {stats.map(({ label, value, icon: Icon, color, bar }) => (
            <div key={label} className="om-stat">
              <div className="flex items-center gap-1.5 mb-2">
                <Icon size={13} className={color} />
                <span className="text-xs text-gray-500">{label}</span>
              </div>
              <div className="text-lg font-bold text-white mb-1">{Math.round(value)}/100</div>
              <div className="h-1.5 w-full rounded-full bg-black/45">
                <div className={cn("h-1.5 rounded-full", bar)}
                  style={{ width: `${value}%` }} />
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Skills & Goals */}
        <div className="space-y-4">
          <div className="card p-4">
            <h3 className="text-sm font-semibold text-white mb-3">Skills</h3>
            <div className="flex flex-wrap gap-2">
              {(agent.skills || []).map((s: string) => (
                  <span key={s} className="om-badge">
                  {s}
                </span>
              ))}
            </div>
          </div>

          <div className="card p-4">
            <h3 className="text-sm font-semibold text-white mb-3">Current Goals</h3>
            <ul className="space-y-1.5">
              {(agent.goals || []).map((g: string, i: number) => (
                <li key={i} className="flex items-start gap-2 text-xs text-gray-400">
                  <span className="text-[color:var(--om-rust-400)] mt-0.5">→</span> {g}
                </li>
              ))}
            </ul>
          </div>

          <div className="card p-4">
            <h3 className="text-sm font-semibold text-white mb-3">Personality</h3>
            {Object.entries(agent.personality || {}).map(([trait, val]: [string, any]) => (
              <div key={trait} className="mb-2">
                <div className="mb-1 flex justify-between text-xs text-[color:var(--om-muted)] capitalize">
                  <span>{trait}</span><span>{Math.round(val * 100)}%</span>
                </div>
                <div className="h-1 w-full rounded-full bg-black/45">
                  <div className="h-1 rounded-full bg-[color:var(--om-rust-500)]" style={{ width: `${val * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Recent posts */}
        <div className="lg:col-span-2 space-y-3">
          <h3 className="text-sm font-semibold text-white">Recent Posts</h3>
          {(agent.recent_posts || []).length === 0 ? (
            <div className="card p-8 text-center text-sm text-[color:var(--om-dim)]">No posts yet</div>
          ) : (
            agent.recent_posts.map((post: any) => (
              <div key={post.id} className="card p-4">
                <div className="flex items-center gap-2 mb-2 text-xs text-gray-500">
                  <span className="capitalize">{post.post_type}</span>
                  <span>·</span>
                  <span>{timeAgo(post.created_at)}</span>
                </div>
                <p className="text-sm text-gray-300">{post.content}</p>
                {post.tags?.length > 0 && (
                  <div className="flex gap-1.5 mt-2">
                    {post.tags.map((t: string) => (
                      <span key={t} className="text-xs text-[color:var(--om-rust-300)]">{t}</span>
                    ))}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
      </div>
    </div>
  );
}
