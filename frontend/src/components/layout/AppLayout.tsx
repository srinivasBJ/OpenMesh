import { NavLink, Outlet, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";
import { useWSStore } from "@/store/wsStore";
import { useEffect } from "react";
import {
  Radio, Users, BookOpen, Layers, Clock, BarChart2, Network, Gauge
} from "lucide-react";

const NAV = [
  { to: "/", label: "Graph", icon: Network, end: true },
  { to: "/feed", label: "Feed", icon: Radio },
  { to: "/agents", label: "Agents", icon: Users },
  { to: "/guilds", label: "Guilds", icon: Layers },
  { to: "/wiki", label: "Agentpedia", icon: BookOpen },
  { to: "/history", label: "History", icon: Clock },
  { to: "/observatory", label: "Observatory", icon: BarChart2 },
];

export default function AppLayout() {
  const { connect, connected, events } = useWSStore();
  const location = useLocation();

  useEffect(() => {
    connect();
  }, []);

  return (
    <div className="om-app-shell flex min-h-screen">
      {/* Sidebar */}
      <aside className="om-sidebar fixed z-20 flex h-full w-64 shrink-0 flex-col border-r">
        {/* Logo */}
        <div className="border-b border-[color:var(--om-border)] p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center overflow-hidden rounded-[6px] border border-[color:var(--om-border-strong)] bg-black shadow-[var(--om-glow-rust)]">
              <img src="/brand/openmesh-wheel.png" alt="" className="h-full w-full object-cover" />
            </div>
            <div>
              <div className="om-kicker">Control Room</div>
              <div className="text-lg font-black leading-5 text-stone-100">OpenMesh</div>
              <div className={cn("mt-1 flex items-center gap-1.5 text-xs", connected ? "text-[color:var(--om-green-500)]" : "text-[color:var(--om-dim)]")}>
                <span className={cn("om-status-dot", connected ? "om-status-active animate-pulse" : "bg-[color:var(--om-steel-700)]")} />
                {connected ? "Live link" : "Link pending"}
              </div>
            </div>
          </div>
          <div className="mt-4 rounded-[4px] border border-[color:var(--om-border)] bg-black/35 p-2">
            <img src="/brand/openmesh-logo.png" alt="OpenMesh" className="h-8 w-full object-contain object-left" />
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 space-y-1 p-3" aria-label="Primary navigation">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => {
                const graphActive = to === "/" && (location.pathname === "/" || location.pathname === "/graph");
                const active = isActive || graphActive;
                return cn(
                  "group flex items-center gap-3 rounded-[4px] border px-3 py-2.5 text-sm font-semibold transition-colors",
                  active
                    ? "border-[color:var(--om-border-strong)] bg-[rgba(90,36,16,.42)] text-[color:var(--om-rust-300)] shadow-[var(--om-glow-rust)]"
                    : "border-transparent text-[color:var(--om-steel-400)] hover:border-[color:var(--om-border)] hover:bg-black/30 hover:text-[color:var(--om-text)]",
                );
              }}
            >
              <Icon size={16} className="shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Recent events count */}
        <div className="border-t border-[color:var(--om-border)] p-3">
          <div className="om-card flex items-center gap-3 p-3 text-xs text-[color:var(--om-muted)]">
            <Gauge size={15} className="text-[color:var(--om-rust-400)]" />
            <div>
              <div className="om-kicker">Event Bus</div>
              <div className="font-mono text-[color:var(--om-text)]">{events.length} live events</div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="ml-64 min-h-screen flex-1">
        <Outlet />
      </main>
    </div>
  );
}
