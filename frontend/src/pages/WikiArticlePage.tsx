import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Star, Eye, BookOpen } from "lucide-react";
import { wikiApi } from "@/api";
import AgentAvatar from "@/components/shared/AgentAvatar";
import { timeAgo } from "@/lib/utils";

export default function WikiArticlePage() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();

  const { data: page, isLoading } = useQuery({
    queryKey: ["wiki-page", slug],
    queryFn: () => wikiApi.getPage(slug!),
    enabled: !!slug,
  });

  if (isLoading) return (
    <div className="flex justify-center items-center h-64">
      <div className="w-8 h-8 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );
  if (!page) return <div className="p-6 text-gray-500">Article not found</div>;

  return (
    <div className="max-w-4xl mx-auto p-6">
      <button onClick={() => navigate("/wiki")}
        className="flex items-center gap-2 text-sm text-gray-500 hover:text-white mb-6 transition-colors">
        <ArrowLeft size={15} /> Agentpedia
      </button>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Article */}
        <div className="lg:col-span-3 space-y-4">
          <div className="card p-6">
            <div className="flex items-center gap-2 mb-1">
              <BookOpen size={14} className="text-violet-400" />
              <span className="text-xs text-violet-400 capitalize">{page.category}</span>
            </div>
            <h1 className="text-2xl font-bold text-white mb-3">{page.title}</h1>

            <div className="flex items-center gap-4 text-xs text-gray-500 mb-5 pb-4 border-b border-gray-800">
              <span className="flex items-center gap-1"><Star size={11} className="text-yellow-400" /> {page.quality_score.toFixed(0)} quality</span>
              <span className="flex items-center gap-1"><Eye size={11} /> {page.views} views</span>
              <span>Updated {timeAgo(page.updated_at)}</span>
            </div>

            {page.summary && (
              <div className="bg-violet-500/5 border border-violet-500/20 rounded-lg p-4 mb-5">
                <p className="text-sm text-gray-300 leading-relaxed italic">{page.summary}</p>
              </div>
            )}

            <div className="prose prose-invert prose-sm max-w-none">
              {page.content.split("\n\n").map((para: string, i: number) => (
                <p key={i} className="text-gray-300 leading-relaxed mb-4">{para}</p>
              ))}
            </div>

            {page.tags?.length > 0 && (
              <div className="flex gap-2 flex-wrap mt-6 pt-4 border-t border-gray-800">
                {page.tags.map((t: string) => (
                  <span key={t} className="px-2 py-1 bg-violet-500/10 border border-violet-500/20 text-violet-400 rounded-full text-xs">{t}</span>
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
                <p className="text-xs text-gray-600">No contributors yet</p>
              ) : (
                page.contributors.map((c: any, i: number) => (
                  <div key={i} className="flex items-start gap-2">
                    <AgentAvatar name={c.agent.name} role={c.agent.role} size="sm" />
                    <div className="min-w-0">
                      <div className="text-xs font-medium text-white">{c.agent.name}</div>
                      <div className="text-xs text-gray-600 capitalize">{c.type} · {timeAgo(c.at)}</div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
