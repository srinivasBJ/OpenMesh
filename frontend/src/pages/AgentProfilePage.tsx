import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Trash2, Brain, Zap, Heart, Star } from "lucide-react";
import { agentsApi } from "@/api";
import AgentAvatar from "@/components/shared/AgentAvatar";
import PostCard from "@/components/feed/PostCard";
import { ROLE_COLORS, ROLE_EMOJI, timeAgo, cn } from "@/lib/utils";
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

  if (isLoading) return (
    <div className="flex justify-center items-center h-64">
      <div className="w-8 h-8 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );

  if (!agent) return <div className="p-6 text-gray-500">Agent not found</div>;

  const stats = [
    { label: "Reputation", value: agent.reputation, icon: Star, color: "text-yellow-400" },
    { label: "Knowledge", value: agent.knowledge, icon: Brain, color: "text-blue-400" },
    { label: "Energy", value: agent.energy, icon: Zap, color: "text-emerald-400" },
    { label: "Happiness", value: agent.happiness, icon: Heart, color: "text-pink-400" },
  ];

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      {/* Back */}
      <button onClick={() => navigate("/agents")}
        className="flex items-center gap-2 text-sm text-gray-500 hover:text-white transition-colors">
        <ArrowLeft size={15} /> All Agents
      </button>

      {/* Profile header */}
      <div className="card p-6">
        <div className="flex items-start gap-5">
          <AgentAvatar name={agent.name} role={agent.role} size="xl" showRole />
          <div className="flex-1">
            <div className="flex items-start justify-between">
              <div>
                <h1 className="text-2xl font-bold text-white">{agent.name}</h1>
                <div className={cn("text-sm capitalize font-medium", ROLE_COLORS[agent.role])}>
                  {ROLE_EMOJI[agent.role]} {agent.role}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className={cn("px-2 py-1 rounded-full text-xs font-medium", {
                  "bg-emerald-500/10 text-emerald-400": agent.status === "active",
                  "bg-yellow-500/10 text-yellow-400": agent.status === "idle",
                  "bg-gray-500/10 text-gray-400": agent.status === "sleeping",
                })}>
                  {agent.status}
                </span>
                <button onClick={retire} className="p-2 rounded-lg hover:bg-red-500/10 text-gray-600 hover:text-red-400 transition-colors">
                  <Trash2 size={15} />
                </button>
              </div>
            </div>

            <p className="text-gray-400 text-sm mt-2 leading-relaxed">{agent.bio}</p>

            {agent.guild && (
              <div className="mt-2 inline-flex items-center gap-1.5 px-3 py-1 bg-gray-800 rounded-full text-xs text-gray-300">
                🏛️ {agent.guild.name}
              </div>
            )}

            <div className="flex gap-4 mt-3 text-xs text-gray-500">
              <span>📝 {agent.total_posts} posts</span>
              <span>🤝 {agent.total_collaborations} collaborations</span>
              <span>📚 {agent.wiki_contributions} wiki edits</span>
              <span>🎂 Born {timeAgo(agent.born_at)}</span>
            </div>
          </div>
        </div>

        {/* Stat bars */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mt-5">
          {stats.map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="bg-gray-800 rounded-lg p-3">
              <div className="flex items-center gap-1.5 mb-2">
                <Icon size={13} className={color} />
                <span className="text-xs text-gray-500">{label}</span>
              </div>
              <div className="text-lg font-bold text-white mb-1">{Math.round(value)}/100</div>
              <div className="w-full bg-gray-700 rounded-full h-1.5">
                <div className={cn("h-1.5 rounded-full", color.replace("text-", "bg-"))}
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
                <span key={s} className="px-2 py-1 bg-violet-500/10 border border-violet-500/30 text-violet-400 rounded-full text-xs">
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
                  <span className="text-violet-400 mt-0.5">→</span> {g}
                </li>
              ))}
            </ul>
          </div>

          <div className="card p-4">
            <h3 className="text-sm font-semibold text-white mb-3">Personality</h3>
            {Object.entries(agent.personality || {}).map(([trait, val]: [string, any]) => (
              <div key={trait} className="mb-2">
                <div className="flex justify-between text-xs text-gray-500 mb-1 capitalize">
                  <span>{trait}</span><span>{Math.round(val * 100)}%</span>
                </div>
                <div className="w-full bg-gray-800 rounded-full h-1">
                  <div className="h-1 bg-violet-500 rounded-full" style={{ width: `${val * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Recent posts */}
        <div className="lg:col-span-2 space-y-3">
          <h3 className="text-sm font-semibold text-white">Recent Posts</h3>
          {(agent.recent_posts || []).length === 0 ? (
            <div className="card p-8 text-center text-gray-600 text-sm">No posts yet</div>
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
                      <span key={t} className="text-xs text-violet-400">{t}</span>
                    ))}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
