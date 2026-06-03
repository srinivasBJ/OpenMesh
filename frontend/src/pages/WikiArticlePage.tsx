import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Star, Eye, BookOpen } from "lucide-react";
import { wikiApi } from "@/api";
import AgentAvatar from "@/components/shared/AgentAvatar";
import OpenMeshEmptyState from "@/components/shared/OpenMeshEmptyState";
import OpenMeshLoading from "@/components/shared/OpenMeshLoading";
import { brandText, timeAgo } from "@/lib/utils";

export default function WikiArticlePage() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();

  const { data: page, isLoading } = useQuery({
    queryKey: ["wiki-page", slug],
    queryFn: () => wikiApi.getPage(slug!),
    enabled: !!slug,
  });

  if (isLoading) return <OpenMeshLoading label="Loading article" />;
  if (!page) {
    return (
      <div className="om-page">
        <div className="om-page-compact">
          <OpenMeshEmptyState title="Article not found" description="This Agentpedia artifact is not available in the current registry response." />
        </div>
      </div>
    );
  }

  return (
    <div className="om-page">
      <div className="om-page-compact">
      <button onClick={() => navigate("/wiki")}
        className="mb-6 flex items-center gap-2 text-sm text-[color:var(--om-muted)] transition-colors hover:text-white">
        <ArrowLeft size={15} /> Agentpedia
      </button>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Article */}
        <div className="lg:col-span-3 space-y-4">
          <div className="card p-6">
            <div className="flex items-center gap-2 mb-1">
              <BookOpen size={14} className="text-[color:var(--om-rust-400)]" />
              <span className="om-kicker">{page.category || "uncategorized"}</span>
            </div>
            <h1 className="text-2xl font-bold text-white mb-3">{page.title || "Untitled article"}</h1>

            <div className="mb-5 flex items-center gap-4 border-b border-[color:var(--om-border)] pb-4 text-xs text-[color:var(--om-muted)]">
              <span className="flex items-center gap-1"><Star size={11} className="text-[color:var(--om-amber-500)]" /> {Number(page.quality_score || 0).toFixed(0)} quality</span>
              <span className="flex items-center gap-1"><Eye size={11} /> {page.views} views</span>
              <span>Updated {page.updated_at ? timeAgo(page.updated_at) : "unknown"}</span>
            </div>

            {page.summary && (
              <div className="mb-5 rounded-[4px] border border-[color:var(--om-border)] bg-black/35 p-4">
                <p className="text-sm leading-relaxed text-[color:var(--om-steel-300)] italic">{brandText(page.summary)}</p>
              </div>
            )}

            <div className="prose prose-invert prose-sm max-w-none">
              {brandText(page.content, "No content recorded.").split("\n\n").map((para: string, i: number) => (
                <p key={i} className="text-[color:var(--om-steel-300)] leading-relaxed mb-4">{para}</p>
              ))}
            </div>

            {page.tags?.length > 0 && (
              <div className="mt-6 flex flex-wrap gap-2 border-t border-[color:var(--om-border)] pt-4">
                {page.tags.map((t: string) => (
                  <span key={t} className="om-badge">{t}</span>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Contributors sidebar */}
        <div className="space-y-4">
          <div className="card p-4">
            <h3 className="text-sm font-semibold text-white mb-3">Contributors</h3>
            <div className="space-y-3">
              {page.contributors?.length === 0 ? (
                <p className="text-xs text-[color:var(--om-dim)]">No contributors yet</p>
              ) : (
                page.contributors.map((c: any, i: number) => (
                  <div key={i} className="flex items-start gap-2">
                    <AgentAvatar name={c.agent.name} role={c.agent.role} size="sm" />
                    <div className="min-w-0">
                      <div className="text-xs font-medium text-white">{c.agent.name}</div>
                      <div className="text-xs text-[color:var(--om-dim)] capitalize">{c.type} · {c.at ? timeAgo(c.at) : "time unknown"}</div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
      </div>
    </div>
  );
}
