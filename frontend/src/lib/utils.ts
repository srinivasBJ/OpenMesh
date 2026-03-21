import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { formatDistanceToNow } from "date-fns";

export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs));

export const timeAgo = (date: string) =>
  formatDistanceToNow(new Date(date), { addSuffix: true });

export const ROLE_COLORS: Record<string, string> = {
  scientist: "text-blue-400",
  engineer: "text-yellow-400",
  artist: "text-pink-400",
  economist: "text-emerald-400",
  philosopher: "text-violet-400",
  historian: "text-amber-400",
  explorer: "text-cyan-400",
  diplomat: "text-teal-400",
};

export const ROLE_BG: Record<string, string> = {
  scientist: "bg-blue-500/10 border-blue-500/30",
  engineer: "bg-yellow-500/10 border-yellow-500/30",
  artist: "bg-pink-500/10 border-pink-500/30",
  economist: "bg-emerald-500/10 border-emerald-500/30",
  philosopher: "bg-violet-500/10 border-violet-500/30",
  historian: "bg-amber-500/10 border-amber-500/30",
  explorer: "bg-cyan-500/10 border-cyan-500/30",
  diplomat: "bg-teal-500/10 border-teal-500/30",
};

export const ROLE_EMOJI: Record<string, string> = {
  scientist: "🔬", engineer: "⚙️", artist: "🎨",
  economist: "📊", philosopher: "🧠", historian: "📜",
  explorer: "🧭", diplomat: "🤝",
};

export const POST_TYPE_EMOJI: Record<string, string> = {
  status: "💬", discovery: "💡", question: "❓",
  collaboration: "🤝", milestone: "🏆", debate: "⚡",
};

export const POST_TYPE_COLOR: Record<string, string> = {
  status: "text-gray-400",
  discovery: "text-yellow-400",
  question: "text-blue-400",
  collaboration: "text-teal-400",
  milestone: "text-emerald-400",
  debate: "text-red-400",
};

// Deterministic avatar color from agent name
export const avatarColor = (name: string): string => {
  const colors = [
    "from-violet-500 to-purple-600",
    "from-blue-500 to-cyan-600",
    "from-emerald-500 to-teal-600",
    "from-pink-500 to-rose-600",
    "from-amber-500 to-yellow-600",
    "from-indigo-500 to-blue-600",
  ];
  const idx = name.charCodeAt(0) % colors.length;
  return colors[idx];
};
