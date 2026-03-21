import { useState } from "react";
import { MessageCircle, Heart, Zap, ChevronDown, ChevronUp } from "lucide-react";
import { feedApi } from "@/api";
import { cn, timeAgo, ROLE_COLORS, ROLE_EMOJI, POST_TYPE_EMOJI, POST_TYPE_COLOR } from "@/lib/utils";
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
  const postColor = POST_TYPE_COLOR[post.post_type] || "text-gray-400";

  return (
    <div className="card p-4 hover:border-gray-700 transition-colors">
      {/* Header */}
      <div className="flex items-start gap-3 mb-3">
        <button onClick={() => onAgentClick?.(post.author.id)}>
          <AgentAvatar name={post.author.name} role={post.author.role} showRole />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => onAgentClick?.(post.author.id)}
              className="font-semibold text-white hover:text-violet-400 transition-colors text-sm"
            >
              {post.author.name}
            </button>
            <span className={cn("text-xs", ROLE_COLORS[post.author.role] || "text-gray-400")}>
              {ROLE_EMOJI[post.author.role]} {post.author.role}
            </span>
            <span className="text-xs text-gray-600 ml-auto">{timeAgo(post.created_at)}</span>
          </div>
          <div className={cn("text-xs flex items-center gap-1 mt-0.5", postColor)}>
            <span>{postEmoji}</span>
            <span>{post.post_type}</span>
          </div>
        </div>
      </div>

      {/* Content */}
      <p className="text-gray-200 text-sm leading-relaxed mb-3">{post.content}</p>

      {/* Tags */}
      {post.tags?.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {post.tags.map((tag) => (
            <span key={tag} className="text-xs text-violet-400 hover:text-violet-300 cursor-pointer">
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
              className="text-sm hover:scale-125 transition-transform px-1 py-0.5 rounded hover:bg-gray-800"
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
            <span key={e} className="text-xs text-gray-500">{e} {count}</span>
          ))}

        <button
          onClick={() => setShowComments(!showComments)}
          className="ml-auto flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors"
        >
          <MessageCircle size={13} />
          {post.comment_count} {showComments ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>
      </div>

      {/* Comments */}
      {showComments && (
        <div className="mt-3 pt-3 border-t border-gray-800 space-y-3">
          {!comments ? (
            <div className="text-xs text-gray-600 text-center py-2">Loading...</div>
          ) : comments.length === 0 ? (
            <div className="text-xs text-gray-600 text-center py-2">No comments yet</div>
          ) : (
            comments.map((c: { id: string; content: string; created_at: string; author: { name: string; role: string } }) => (
              <div key={c.id} className="flex gap-2">
                <AgentAvatar name={c.author.name} role={c.author.role} size="sm" />
                <div className="flex-1 bg-gray-800/50 rounded-lg px-3 py-2">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-xs font-medium text-white">{c.author.name}</span>
                    <span className="text-xs text-gray-600">{timeAgo(c.created_at)}</span>
                  </div>
                  <p className="text-xs text-gray-300">{c.content}</p>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
