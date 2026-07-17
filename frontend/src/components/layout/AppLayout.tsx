import { NavLink, Outlet, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";
import { useWSStore } from "@/store/wsStore";
import { useEffect, useState, type MouseEvent as ReactMouseEvent } from "react";
import {
  Radio, Users, BookOpen, Layers, Clock, BarChart2, Network, Gauge, PanelLeftClose, PanelLeftOpen, Moon, Sun
} from "lucide-react";
import RouteErrorBoundary from "@/components/shared/RouteErrorBoundary";
import RotatingOrb from "@/components/shared/RotatingOrb";
import TopBar from "@/components/layout/TopBar";
import WorkspaceSelector from "@/components/workspace/WorkspaceSelector";
import CreateProjectModal from "@/components/workspace/CreateProjectModal";
import DemoBanner from "@/components/workspace/DemoBanner";

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
const THEME_KEY = "openmesh.theme";
const SIDEBAR_MIN = 300;
const SIDEBAR_MAX = 430;
const SIDEBAR_COLLAPSED = 92;

function readStoredWidth() {
  const value = Number(window.localStorage.getItem(SIDEBAR_WIDTH_KEY));
  return Number.isFinite(value) ? clamp(value, SIDEBAR_MIN, SIDEBAR_MAX) : 320;
}

function readStoredCollapsed() {
  return window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "true";
}

function readStoredTheme() {
  return window.localStorage.getItem(THEME_KEY) === "light" ? "light" : "dark";
}

export default function AppLayout() {
  const { connect, connected, events } = useWSStore();
  const location = useLocation();
  const [sidebarWidth, setSidebarWidth] = useState(readStoredWidth);
  const [collapsed, setCollapsed] = useState(readStoredCollapsed);
  const [theme, setTheme] = useState<"light" | "dark">(readStoredTheme);
  const [createOpen, setCreateOpen] = useState(false);
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

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

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
        <div className={cn("w-full border-b border-[color:var(--om-border)] p-5", collapsed ? "px-3" : "p-6")}>
          <div className={cn("flex items-center", collapsed ? "justify-center" : "gap-4")}>
            <RotatingOrb size={64} className="drop-shadow-[0_0_14px_rgba(190,92,36,.32)]" />
            {!collapsed ? (
            <div className="min-w-0">
              <div className="om-kicker">Control Room</div>
              <div className="text-xl font-black leading-6 text-stone-100">OpenMesh</div>
              <div className={cn("mt-1.5 flex items-center gap-2 text-sm", connected ? "text-[color:var(--om-green-500)]" : "text-[color:var(--om-dim)]")}>
                <span className={cn("om-status-dot", connected ? "om-status-active animate-pulse" : "bg-[color:var(--om-steel-700)]")} />
                {connected ? "Live link" : "Link pending"}
              </div>
            </div>
            ) : null}
          </div>
          <div className={cn("mt-5 flex gap-3", collapsed ? "justify-center" : "justify-between")}>
            <button
              type="button"
              className="om-button-ghost h-10 w-10 p-0"
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              onClick={() => setCollapsed((value) => !value)}
            >
              {collapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}
            </button>
            <button
              type="button"
              className={cn("om-button-ghost h-10", collapsed ? "w-10 p-0" : "px-4")}
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
              title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
              onClick={() => setTheme((value) => (value === "dark" ? "light" : "dark"))}
            >
              {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
              {!collapsed ? <span className="text-sm capitalize">{theme}</span> : null}
            </button>
          </div>
        </div>

        {/* Nav */}
        <nav className={cn("w-full flex-1 space-y-3 p-5", collapsed && "px-3")} aria-label="Primary navigation">
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
                  collapsed ? "h-[3.25rem] min-h-[3.25rem] justify-center px-0" : "gap-4 px-5 py-4 text-[0.95rem]",
                  active
                    ? "border-[color:var(--om-border-strong)] bg-[rgba(90,36,16,.42)] text-[color:var(--om-rust-300)] shadow-[var(--om-glow-rust)]"
                    : "border-transparent text-[color:var(--om-steel-400)] hover:border-[color:var(--om-border)] hover:bg-black/30 hover:text-[color:var(--om-text)]",
                );
              }}
            >
              <Icon size={18} className="shrink-0" />
              {!collapsed ? <span className="truncate">{label}</span> : null}
            </NavLink>
          ))}
        </nav>

        {/* Event bus + workspace selector */}
        <div className={cn("w-full border-t border-[color:var(--om-border)] p-5", collapsed && "px-3")}>
          <div className={cn("om-card text-sm text-[color:var(--om-muted)]", collapsed ? "flex items-center justify-center p-3" : "p-5")}>
            <div className={cn("flex items-center", collapsed ? "justify-center" : "gap-4")}>
              <Gauge size={17} className="text-[color:var(--om-rust-400)]" />
              {!collapsed ? (
              <div className="min-w-0">
                <div className="om-kicker">Event Bus</div>
                <div className="font-mono text-[color:var(--om-text)]">{events.length} live events</div>
              </div>
              ) : null}
            </div>
            {!collapsed ? (
              <>
                <div className="om-kicker mt-4">Workspace</div>
                <WorkspaceSelector onCreate={() => setCreateOpen(true)} />
              </>
            ) : null}
          </div>
        </div>
        {!collapsed ? <div className="om-sidebar-resize" onMouseDown={startResize} aria-hidden="true" /> : null}
      </aside>

      {/* Main */}
      <main className="min-h-screen flex-1 transition-[margin] duration-200" style={{ marginLeft: effectiveWidth }}>
        <TopBar />
        <DemoBanner />
        <RouteErrorBoundary resetKey={location.pathname}>
          <Outlet />
        </RouteErrorBoundary>
      </main>
      {createOpen ? <CreateProjectModal onClose={() => setCreateOpen(false)} /> : null}
    </div>
  );
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}
