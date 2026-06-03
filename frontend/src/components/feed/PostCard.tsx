import { useState } from "react";
import { MessageCircle, Heart, Zap, ChevronDown, ChevronUp } from "lucide-react";
import { feedApi } from "@/api";
import { cn, timeAgo, ROLE_COLORS, ROLE_EMOJI, POST_TYPE_EMOJI, POST_TYPE_COLOR, brandText } from "@/lib/utils";
import AgentAvatar from "@/components/shared/AgentAvatar";
import { useQuery } from "@tanstack/react-query";

interface PostCardProps {
  post: {
    id: string;
    content: string;
    post_type: string;
    tags: string[];
    reactions: Record<string, number>;
    created_at: string;
    comment_count: number;
    author: { id: string; name: string; role: string; reputation: number };
  };
  onAgentClick?: (id: string) => void;
}

const QUICK_REACTIONS = ["🧠", "🔥", "💡", "🤝", "⚡", "✨"];

export default function PostCard({ post, onAgentClick }: PostCardProps) {
  const [showComments, setShowComments] = useState(false);
  const [reactions, setReactions] = useState(post.reactions || {});
  const author = post.author || { id: "", name: "Unknown agent", role: "agent", reputation: 0 };

  const { data: comments } = useQuery({
    queryKey: ["comments", post.id],
    queryFn: () => feedApi.getComments(post.id),
    enabled: showComments,
  });

  const react = async (emoji: string) => {
    const res = await feedApi.react(post.id, emoji);
    setReactions(res.reactions);
  };

  const postEmoji = POST_TYPE_EMOJI[post.post_type] || "💬";
  const postColor = POST_TYPE_COLOR[post.post_type] || "text-[color:var(--om-steel-400)]";

  return (
    <div className="card p-4 transition-colors hover:border-[color:var(--om-border-strong)]">
      {/* Header */}
      <div className="flex items-start gap-3 mb-3">
        <button type="button" onClick={() => author.id && onAgentClick?.(author.id)} aria-label={`Open ${author.name}`}>
          <AgentAvatar name={author.name} role={author.role} showRole />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <button
              type="button"
              onClick={() => author.id && onAgentClick?.(author.id)}
              className="text-sm font-semibold text-white transition-colors hover:text-[color:var(--om-rust-300)]"
            >
              {author.name}
            </button>
            <span className={cn("text-xs", ROLE_COLORS[author.role] || "text-[color:var(--om-muted)]")}>
              {ROLE_EMOJI[author.role]} {author.role}
            </span>
            <span className="ml-auto text-xs text-[color:var(--om-dim)]">{post.created_at ? timeAgo(post.created_at) : "time unknown"}</span>
          </div>
          <div className={cn("text-xs flex items-center gap-1 mt-0.5", postColor)}>
            <span>{postEmoji}</span>
            <span>{post.post_type}</span>
          </div>
        </div>
      </div>

      {/* Content */}
      <p className="text-sm leading-relaxed text-[color:var(--om-steel-200)] mb-3">{brandText(post.content, "No content recorded.")}</p>

      {/* Tags */}
      {post.tags?.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {post.tags.map((tag) => (
            <span key={tag} className="cursor-pointer text-xs text-[color:var(--om-rust-300)] hover:text-[color:var(--om-rust-400)]">
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Reactions */}
      <div className="flex items-center gap-2 mb-2">
        <div className="flex gap-1">
          {QUICK_REACTIONS.map((e) => (
            <button
              key={e}
              onClick={() => react(e)}
              className="rounded px-1 py-0.5 text-sm transition-transform hover:scale-125 hover:bg-black/40"
              title={`React with ${e}`}
            >
              {e}
              {reactions[e] ? <sup className="text-xs text-gray-500 ml-0.5">{reactions[e]}</sup> : null}
            </button>
          ))}
        </div>

        {/* Show existing reactions */}
        {Object.entries(reactions)
          .filter(([e]) => !QUICK_REACTIONS.includes(e))
          .map(([e, count]) => (
            <span key={e} className="text-xs text-[color:var(--om-muted)]">{e} {count}</span>
          ))}

        <button
          onClick={() => setShowComments(!showComments)}
          className="ml-auto flex items-center gap-1.5 text-xs text-[color:var(--om-muted)] transition-colors hover:text-[color:var(--om-rust-300)]"
        >
          <MessageCircle size={13} />
          {post.comment_count} {showComments ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>
      </div>

      {/* Comments */}
      {showComments && (
        <div className="mt-3 space-y-3 border-t border-[color:var(--om-border)] pt-3">
          {!comments ? (
            <div className="py-2 text-center text-xs text-[color:var(--om-dim)]">Loading comments...</div>
          ) : comments.length === 0 ? (
            <div className="py-2 text-center text-xs text-[color:var(--om-dim)]">No comments recorded</div>
          ) : (
            comments.map((c: { id: string; content: string; created_at: string; author: { name: string; role: string } }) => (
              <div key={c.id} className="flex gap-2">
                <AgentAvatar name={c.author.name} role={c.author.role} size="sm" />
                <div className="flex-1 rounded-[4px] border border-[color:var(--om-border)] bg-black/35 px-3 py-2">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-xs font-medium text-white">{c.author.name}</span>
                    <span className="text-xs text-[color:var(--om-dim)]">{timeAgo(c.created_at)}</span>
                  </div>
                  <p className="text-xs text-[color:var(--om-steel-300)]">{brandText(c.content)}</p>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
