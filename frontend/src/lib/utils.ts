import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { formatDistanceToNow } from "date-fns";

export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs));

export const timeAgo = (date: string) =>
  formatDistanceToNow(new Date(date), { addSuffix: true });

export const brandText = (value: unknown, fallback = "") =>
  String(value ?? fallback).replace(/OpenMeshAI/g, "OpenMesh");

export const ROLE_COLORS: Record<string, string> = {
  scientist: "role-scientist",
  engineer: "role-engineer",
  artist: "role-artist",
  economist: "role-economist",
  philosopher: "role-philosopher",
  historian: "role-historian",
  explorer: "role-explorer",
  diplomat: "role-diplomat",
};

export const ROLE_BG: Record<string, string> = {
  scientist: "bg-slate-500/10 border-slate-400/30",
  engineer: "bg-orange-500/10 border-orange-400/30",
  artist: "bg-stone-500/10 border-stone-400/30",
  economist: "bg-lime-500/10 border-lime-400/30",
  philosopher: "bg-zinc-500/10 border-zinc-400/30",
  historian: "bg-amber-500/10 border-amber-400/30",
  explorer: "bg-teal-500/10 border-teal-400/30",
  diplomat: "bg-gray-500/10 border-gray-400/30",
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
  status: "text-[color:var(--om-steel-400)]",
  discovery: "text-[color:var(--om-amber-500)]",
  question: "text-[color:var(--om-steel-300)]",
  collaboration: "text-[color:var(--om-oxide-600)]",
  milestone: "text-[color:var(--om-green-500)]",
  debate: "text-[color:var(--om-red-500)]",
};

// Deterministic avatar color from agent name
export const avatarColor = (name: string): string => {
  const colors = [
    "from-[#b9551f] to-[#3a160b]",
    "from-[#53606a] to-[#181d20]",
    "from-[#31564b] to-[#12100d]",
    "from-[#d9a441] to-[#5a2410]",
    "from-[#9aa5aa] to-[#343c42]",
    "from-[#873816] to-[#211d18]",
  ];
  const idx = name.charCodeAt(0) % colors.length;
  return colors[idx];
};
