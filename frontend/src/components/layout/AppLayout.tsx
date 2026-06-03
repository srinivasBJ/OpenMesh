import { NavLink, Outlet, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";
import { useWSStore } from "@/store/wsStore";
import { useEffect, useState, type MouseEvent as ReactMouseEvent } from "react";
import {
  Radio, Users, BookOpen, Layers, Clock, BarChart2, Network, Gauge, PanelLeftClose, PanelLeftOpen
} from "lucide-react";
import RouteErrorBoundary from "@/components/shared/RouteErrorBoundary";

const NAV = [
  { to: "/", label: "Graph", icon: Network, end: true },
  { to: "/feed", label: "Feed", icon: Radio },
  { to: "/agents", label: "Agents", icon: Users },
  { to: "/guilds", label: "Guilds", icon: Layers },
  { to: "/wiki", label: "Agentpedia", icon: BookOpen },
  { to: "/history", label: "History", icon: Clock },
  { to: "/observatory", label: "Observatory", icon: BarChart2 },
];

const SIDEBAR_WIDTH_KEY = "openmesh.sidebar.width";
const SIDEBAR_COLLAPSED_KEY = "openmesh.sidebar.collapsed";
const SIDEBAR_MIN = 212;
const SIDEBAR_MAX = 340;
const SIDEBAR_COLLAPSED = 76;

function readStoredWidth() {
  const value = Number(window.localStorage.getItem(SIDEBAR_WIDTH_KEY));
  return Number.isFinite(value) ? clamp(value, SIDEBAR_MIN, SIDEBAR_MAX) : 256;
}

function readStoredCollapsed() {
  return window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "true";
}

export default function AppLayout() {
  const { connect, connected, events } = useWSStore();
  const location = useLocation();
  const [sidebarWidth, setSidebarWidth] = useState(readStoredWidth);
  const [collapsed, setCollapsed] = useState(readStoredCollapsed);
  const effectiveWidth = collapsed ? SIDEBAR_COLLAPSED : sidebarWidth;

  useEffect(() => {
    connect();
  }, []);

  useEffect(() => {
    window.localStorage.setItem(SIDEBAR_WIDTH_KEY, String(sidebarWidth));
  }, [sidebarWidth]);

  useEffect(() => {
    window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(collapsed));
  }, [collapsed]);

  const startResize = (event: ReactMouseEvent<HTMLDivElement>) => {
    if (collapsed) return;
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = sidebarWidth;

    const onMove = (moveEvent: MouseEvent) => {
      setSidebarWidth(clamp(startWidth + moveEvent.clientX - startX, SIDEBAR_MIN, SIDEBAR_MAX));
    };
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };

  return (
    <div className="om-app-shell flex min-h-screen">
      {/* Sidebar */}
      <aside
        className={cn("om-sidebar fixed z-20 flex h-full shrink-0 flex-col border-r", collapsed && "items-center")}
        style={{ width: effectiveWidth }}
      >
        {/* Logo */}
        <div className={cn("w-full border-b border-[color:var(--om-border)] p-3", collapsed ? "px-2" : "p-4")}>
          <div className={cn("flex items-center", collapsed ? "justify-center" : "gap-3")}>
            <div className="flex h-12 w-12 items-center justify-center overflow-hidden rounded-[6px] border border-[color:var(--om-border-strong)] bg-black shadow-[var(--om-glow-rust)]">
              <img src="/brand/openmesh-wheel.png" alt="" className="h-full w-full object-cover" />
            </div>
            {!collapsed ? (
            <div className="min-w-0">
              <div className="om-kicker">Control Room</div>
              <div className="text-lg font-black leading-5 text-stone-100">OpenMesh</div>
              <div className={cn("mt-1 flex items-center gap-1.5 text-xs", connected ? "text-[color:var(--om-green-500)]" : "text-[color:var(--om-dim)]")}>
                <span className={cn("om-status-dot", connected ? "om-status-active animate-pulse" : "bg-[color:var(--om-steel-700)]")} />
                {connected ? "Live link" : "Link pending"}
              </div>
            </div>
            ) : null}
          </div>
          <div className={cn("mt-3 flex", collapsed ? "justify-center" : "justify-between")}>
            <button
              type="button"
              className="om-button-ghost h-9 w-9 p-0"
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              onClick={() => setCollapsed((value) => !value)}
            >
              {collapsed ? <PanelLeftOpen size={15} /> : <PanelLeftClose size={15} />}
            </button>
          </div>
        </div>

        {/* Nav */}
        <nav className={cn("w-full flex-1 space-y-1 p-3", collapsed && "px-2")} aria-label="Primary navigation">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              aria-label={label}
              title={collapsed ? label : undefined}
              className={({ isActive }) => {
                const graphActive = to === "/" && (location.pathname === "/" || location.pathname === "/graph");
                const active = isActive || graphActive;
                return cn(
                  "group flex items-center rounded-[4px] border text-sm font-semibold transition-colors",
                  collapsed ? "h-11 justify-center px-0" : "gap-3 px-3 py-2.5",
                  active
                    ? "border-[color:var(--om-border-strong)] bg-[rgba(90,36,16,.42)] text-[color:var(--om-rust-300)] shadow-[var(--om-glow-rust)]"
                    : "border-transparent text-[color:var(--om-steel-400)] hover:border-[color:var(--om-border)] hover:bg-black/30 hover:text-[color:var(--om-text)]",
                );
              }}
            >
              <Icon size={16} className="shrink-0" />
              {!collapsed ? <span className="truncate">{label}</span> : null}
            </NavLink>
          ))}
        </nav>

        {/* Recent events count */}
        <div className={cn("w-full border-t border-[color:var(--om-border)] p-3", collapsed && "px-2")}>
          <div className={cn("om-card flex items-center text-xs text-[color:var(--om-muted)]", collapsed ? "justify-center p-2" : "gap-3 p-3")}>
            <Gauge size={15} className="text-[color:var(--om-rust-400)]" />
            {!collapsed ? (
            <div className="min-w-0">
              <div className="om-kicker">Event Bus</div>
              <div className="font-mono text-[color:var(--om-text)]">{events.length} live events</div>
            </div>
            ) : null}
          </div>
        </div>
        {!collapsed ? <div className="om-sidebar-resize" onMouseDown={startResize} aria-hidden="true" /> : null}
      </aside>

      {/* Main */}
      <main className="min-h-screen flex-1 transition-[margin] duration-200" style={{ marginLeft: effectiveWidth }}>
        <RouteErrorBoundary resetKey={location.pathname}>
          <Outlet />
        </RouteErrorBoundary>
      </main>
    </div>
  );
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}
