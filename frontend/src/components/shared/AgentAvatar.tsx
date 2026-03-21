import { ROLE_EMOJI, avatarColor } from "@/lib/utils";
import { cn } from "@/lib/utils";

interface AgentAvatarProps {
  name: string;
  role: string;
  size?: "sm" | "md" | "lg" | "xl";
  showRole?: boolean;
}

const sizes = {
  sm: "w-8 h-8 text-sm",
  md: "w-10 h-10 text-base",
  lg: "w-14 h-14 text-xl",
  xl: "w-20 h-20 text-3xl",
};

export default function AgentAvatar({ name, role, size = "md", showRole = false }: AgentAvatarProps) {
  const gradient = avatarColor(name);
  const emoji = ROLE_EMOJI[role] || "🤖";
  const initials = name.split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase();

  return (
    <div className="relative inline-block">
      <div className={cn(
        "rounded-full bg-gradient-to-br flex items-center justify-center font-bold text-white shrink-0",
        `bg-gradient-to-br ${gradient}`,
        sizes[size]
      )}>
        {initials}
      </div>
      {showRole && (
        <div className="absolute -bottom-0.5 -right-0.5 text-xs leading-none">
          {emoji}
        </div>
      )}
    </div>
  );
}
