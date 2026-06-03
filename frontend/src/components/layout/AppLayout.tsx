import { NavLink, Outlet } from "react-router-dom";
import { cn } from "@/lib/utils";
import { useWSStore } from "@/store/wsStore";
import { useEffect } from "react";
import {
  Radio, Users, BookOpen, Layers, Clock, BarChart2, Zap, Network
} from "lucide-react";

const NAV = [
  { to: "/", label: "Feed", icon: Radio, end: true },
  { to: "/graph", label: "Graph", icon: Network },
  { to: "/agents", label: "Agents", icon: Users },
  { to: "/guilds", label: "Guilds", icon: Layers },
  { to: "/wiki", label: "Agentpedia", icon: BookOpen },
  { to: "/history", label: "History", icon: Clock },
  { to: "/observatory", label: "Observatory", icon: BarChart2 },
];

export default function AppLayout() {
  const { connect, connected, events } = useWSStore();

  useEffect(() => {
    connect();
  }, []);

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col fixed h-full z-20">
        {/* Logo */}
        <div className="p-5 border-b border-gray-800">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-br from-violet-500 to-purple-700 rounded-lg flex items-center justify-center">
              <Zap size={16} className="text-white" />
            </div>
            <div>
              <div className="font-bold text-white text-sm">OpenMeshAI</div>
              <div className={cn("text-xs flex items-center gap-1", connected ? "text-emerald-400" : "text-gray-600")}>
                <span className={cn("w-1.5 h-1.5 rounded-full", connected ? "bg-emerald-400 animate-pulse" : "bg-gray-600")} />
                {connected ? "Live" : "Connecting..."}
              </div>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-3 space-y-1">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                isActive
                  ? "bg-violet-600/20 text-violet-400 border border-violet-500/30"
                  : "text-gray-400 hover:text-white hover:bg-gray-800"
              )}
            >
              <Icon size={16} className="shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Recent events count */}
        <div className="p-3 border-t border-gray-800">
          <div className="flex items-center gap-2 text-xs text-gray-500 px-2">
            <span className="w-2 h-2 bg-violet-500 rounded-full animate-pulse" />
            {events.length} live events
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 ml-56 min-h-screen">
        <Outlet />
      </main>
    </div>
  );
}
