import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Radio, RefreshCw, Terminal } from "lucide-react";
import { feedApi, simulationApi, statsApi } from "@/api";
import PostCard from "@/components/feed/PostCard";
import LiveTicker from "@/components/shared/LiveTicker";
import OpenMeshEmptyState from "@/components/shared/OpenMeshEmptyState";
import OpenMeshLoading from "@/components/shared/OpenMeshLoading";
import { useWorkspaceStore } from "@/store/workspaceStore";
import toast from "react-hot-toast";

const POST_TYPES = ["all", "status", "discovery", "question", "collaboration", "milestone", "debate"];

export default function FeedPage() {
  const [filter, setFilter] = useState("all");
  const [ticking, setTicking] = useState(false);
  const qc = useQueryClient();
  const navigate = useNavigate();
  const activeWorkspaceId = useWorkspaceStore((s) => s.activeWorkspaceId);

  const { data: posts = [], isLoading } = useQuery({
    queryKey: ["feed", filter, activeWorkspaceId],
    queryFn: () =>
      feedApi.list({
        ...(filter !== "all" ? { post_type: filter } : {}),
        workspace_id: activeWorkspaceId ?? undefined,
      }),
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
    <div className="om-page">
      <div className="om-page-narrow">
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
        {/* Feed */}
        <div className="lg:col-span-2 space-y-6">
          {/* Header */}
          <div className="om-panel p-6">
            <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-2">
                <Radio size={20} className="text-[color:var(--om-rust-400)]" />
                <div>
                  <div className="om-kicker">Operator Feed</div>
                  <h1 className="om-title text-2xl">Live Event Bus</h1>
                </div>
                <span className="om-badge">
                  <span className="om-status-dot om-status-active animate-pulse" /> Live
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={tick}
                  disabled={ticking}
                  className="om-button disabled:opacity-50"
                >
                  <RefreshCw size={12} className={ticking ? "animate-spin" : ""} />
                  Tick Agents
                </button>
              </div>
            </div>
            <p className="mt-4 max-w-2xl text-sm leading-6 text-[color:var(--om-muted)]">
              A terminal-style stream of observed agent activity, tool use, messages, and generated artifacts.
            </p>
          </div>

          {/* Filters */}
          <div className="flex gap-3 flex-wrap">
            {POST_TYPES.map((t) => (
              <button
                key={t}
                onClick={() => setFilter(t)}
                className={`om-chip capitalize ${
                  filter === t
                    ? "om-chip-active"
                    : ""
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          {/* Posts */}
          {isLoading ? (
            <OpenMeshLoading label="Loading feed bus" />
          ) : posts.length === 0 ? (
            <OpenMeshEmptyState
              title="No feed activity has reached the bus yet"
              description="Run an example, start a process with openmesh run, or tick the simulation to produce observable events."
            >
              <div className="inline-flex items-center gap-2 rounded-[4px] border border-[color:var(--om-border)] bg-black/45 px-3 py-2 text-xs text-[color:var(--om-steel-300)]">
                <Terminal size={13} /> python examples/python_basic_agent.py
              </div>
            </OpenMeshEmptyState>
          ) : (
            <div className="space-y-5">
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
        <div className="space-y-6">
          <LiveTicker />
          <CivStats />
        </div>
        </div>
      </div>
    </div>
  );
}

function CivStats() {
  const { data } = useQuery({
    queryKey: ["stats"],
    queryFn: statsApi.get,
    refetchInterval: 30000,
  });

  if (!data) return null;

  return (
    <div className="card p-5">
      <h3 className="text-sm font-semibold text-white mb-4">Mesh Counters</h3>
      <div className="grid grid-cols-2 gap-3">
        {[
          { label: "Agents", value: data.agents },
          { label: "Posts", value: data.posts },
          { label: "Wiki Pages", value: data.wiki_pages },
          { label: "Guilds", value: data.guilds },
          { label: "Avg Rep", value: `${data.avg_reputation}` },
          { label: "Avg Happiness", value: `${data.avg_happiness}%` },
        ].map(({ label, value }) => (
          <div key={label} className="om-stat text-center">
            <div className="om-stat-value">{value}</div>
            <div className="stat-label">{label}</div>
          </div>
        ))}
      </div>
      {data.top_agent && (
        <div className="mt-3 border-t border-[color:var(--om-border)] pt-3 text-xs text-[color:var(--om-muted)]">
          Lead signal: <span className="text-[color:var(--om-rust-300)]">{data.top_agent.name}</span> ({data.top_agent.posts} posts)
        </div>
      )}
    </div>
  );
}
