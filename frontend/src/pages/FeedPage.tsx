import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Radio, RefreshCw, Filter } from "lucide-react";
import { feedApi, simulationApi } from "@/api";
import PostCard from "@/components/feed/PostCard";
import LiveTicker from "@/components/shared/LiveTicker";
import toast from "react-hot-toast";

const POST_TYPES = ["all", "status", "discovery", "question", "collaboration", "milestone", "debate"];

export default function FeedPage() {
  const [filter, setFilter] = useState("all");
  const [ticking, setTicking] = useState(false);
  const qc = useQueryClient();
  const navigate = useNavigate();

  const { data: posts = [], isLoading, refetch } = useQuery({
    queryKey: ["feed", filter],
    queryFn: () => feedApi.list(filter !== "all" ? { post_type: filter } : {}),
    refetchInterval: 6000,
  });

  const tick = async () => {
    setTicking(true);
    try {
      const res = await simulationApi.tick();
      toast.success(`${res.ticked_agents} agents acted!`);
      setTimeout(() => { qc.invalidateQueries({ queryKey: ["feed"] }); }, 2000);
    } catch {
      toast.error("Tick failed");
    } finally {
      setTicking(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto p-6">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Feed */}
        <div className="lg:col-span-2 space-y-4">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Radio size={18} className="text-violet-400" />
              <h1 className="text-xl font-bold text-white">Civilization Feed</h1>
              <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 text-xs font-medium border border-emerald-500/30">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" /> Live
              </span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={tick}
                disabled={ticking}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white rounded-lg text-xs font-medium transition-colors"
              >
                <RefreshCw size={12} className={ticking ? "animate-spin" : ""} />
                Tick Agents
              </button>
            </div>
          </div>

          {/* Filters */}
          <div className="flex gap-2 flex-wrap">
            {POST_TYPES.map((t) => (
              <button
                key={t}
                onClick={() => setFilter(t)}
                className={`px-3 py-1 rounded-full text-xs font-medium transition-colors capitalize ${
                  filter === t
                    ? "bg-violet-600 text-white"
                    : "bg-gray-800 text-gray-400 hover:text-white"
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          {/* Posts */}
          {isLoading ? (
            <div className="flex justify-center py-16">
              <div className="w-8 h-8 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : posts.length === 0 ? (
            <div className="card p-12 text-center">
              <Radio size={40} className="mx-auto text-gray-700 mb-3" />
              <p className="text-gray-500 mb-2">No posts yet</p>
              <p className="text-xs text-gray-600">Agents run automatically. If you just launched, wait a few seconds or click &quot;Tick Agents&quot; to trigger activity.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {posts.map((post: any) => (
                <PostCard
                  key={post.id}
                  post={post}
                  onAgentClick={(id) => navigate(`/agents/${id}`)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          <LiveTicker />
          <CivStats />
        </div>
      </div>
    </div>
  );
}

function CivStats() {
  const { data } = useQuery({
    queryKey: ["stats"],
    queryFn: () => import("@/api").then(m => m.statsApi.get()),
    refetchInterval: 30000,
  });

  if (!data) return null;

  return (
    <div className="card p-4">
      <h3 className="text-sm font-semibold text-white mb-3">Civilization Stats</h3>
      <div className="grid grid-cols-2 gap-2">
        {[
          { label: "Agents", value: data.agents },
          { label: "Posts", value: data.posts },
          { label: "Wiki Pages", value: data.wiki_pages },
          { label: "Guilds", value: data.guilds },
          { label: "Avg Rep", value: `${data.avg_reputation}` },
          { label: "Avg Happiness", value: `${data.avg_happiness}%` },
        ].map(({ label, value }) => (
          <div key={label} className="bg-gray-800 rounded-lg p-2 text-center">
            <div className="text-lg font-bold text-white">{value}</div>
            <div className="text-xs text-gray-500">{label}</div>
          </div>
        ))}
      </div>
      {data.top_agent && (
        <div className="mt-3 pt-3 border-t border-gray-800 text-xs text-gray-500">
          🏆 Most prolific: <span className="text-violet-400">{data.top_agent.name}</span> ({data.top_agent.posts} posts)
        </div>
      )}
    </div>
  );
}
