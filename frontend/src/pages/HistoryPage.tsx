import { useQuery } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { AlertTriangle, Baby, BookOpen, Clock, GitBranch, Layers, Pause, Play, Radio, SkipBack, SkipForward, Star, Users, Zap } from "lucide-react";
import { eventsApi, openmeshApi } from "@/api";
import OpenMeshEmptyState from "@/components/shared/OpenMeshEmptyState";
import OpenMeshLoading from "@/components/shared/OpenMeshLoading";
import { brandText, cn, timeAgo } from "@/lib/utils";
import type { OpenMeshReplay, OpenMeshReplayFrame, OpenMeshTimeline, OpenMeshTraceSummary } from "@/types/openmesh";

const EVENT_ICONS: Record<string, any> = {
  birth: Baby, guild_founded: Layers, discovery: Zap,
  collaboration: Users, milestone: Star, wiki_created: BookOpen,
  wiki_edit: BookOpen, retirement: Clock,
};

const EVENT_COLORS: Record<string, string> = {
  birth: "text-[color:var(--om-green-500)] bg-black/40 border-[color:var(--om-green-500)]/40",
  guild_founded: "text-[color:var(--om-rust-300)] bg-black/40 border-[color:var(--om-rust-500)]/40",
  discovery: "text-[color:var(--om-amber-500)] bg-black/40 border-[color:var(--om-amber-500)]/40",
  milestone: "text-[color:var(--om-steel-300)] bg-black/40 border-[color:var(--om-steel-500)]/40",
  wiki_created: "text-[color:var(--om-oxide-600)] bg-black/40 border-[color:var(--om-oxide-600)]/40",
  wiki_edit: "text-[color:var(--om-muted)] bg-black/40 border-[color:var(--om-border)]",
  retirement: "text-[color:var(--om-red-500)] bg-black/40 border-[color:var(--om-red-500)]/40",
};

export default function HistoryPage() {
  const [replayControl, setReplayControl] = useState<"start" | "pause" | "step" | "previous" | "stop">("pause");
  const [replayPosition, setReplayPosition] = useState(0);
  const [replaySpeed, setReplaySpeed] = useState(1);
  const {
    data: events = [],
    isLoading: eventsLoading,
    isError: eventsError,
    refetch: refetchEvents,
  } = useQuery({
    queryKey: ["events"],
    queryFn: () => eventsApi.list(100),
    refetchInterval: 15000,
  });
  const {
    data: traces = [],
    isLoading: tracesLoading,
    isError: tracesError,
    refetch: refetchTraces,
  } = useQuery({
    queryKey: ["openmesh-history-traces"],
    queryFn: () => openmeshApi.traces(80),
    refetchInterval: 15000,
  });
  const {
    data: timeline,
    isLoading: timelineLoading,
    isError: timelineError,
    refetch: refetchTimeline,
  } = useQuery({
    queryKey: ["openmesh-history-timeline"],
    queryFn: () => openmeshApi.timeline(500),
    refetchInterval: 15000,
  });
  const { data: replay } = useQuery({
    queryKey: ["openmesh-history-replay", replayControl, replayPosition, replaySpeed],
    queryFn: () =>
      openmeshApi.replayEcosystem({
        control: replayControl,
        position: replayPosition,
        speed: replaySpeed,
        limit: 500,
      }),
    refetchInterval: false,
  });

  useEffect(() => {
    if (replayControl !== "start") return undefined;
    const interval = window.setInterval(() => {
      setReplayPosition((position) => {
        const maxPosition = Math.max((replay?.state?.frame_count || 1) - 1, 0);
        return Math.min(position + 1, maxPosition);
      });
    }, Math.max(300, 1200 / replaySpeed));
    return () => window.clearInterval(interval);
  }, [replayControl, replaySpeed, replay?.state?.frame_count]);

  const traceList = Array.isArray(traces) ? traces : [];
  const eventList = Array.isArray(events) ? events : [];
  const timelineRows = collectTimelineRows(timeline);
  const isLoading = eventsLoading || tracesLoading || timelineLoading;
  const hasError = eventsError || tracesError || timelineError;
  const hasContent = traceList.length > 0 || timelineRows.length > 0 || eventList.length > 0;
  const refetchAll = () => {
    void refetchEvents();
    void refetchTraces();
    void refetchTimeline();
  };

  return (
    <div className="om-page">
      <div className="om-page-wide space-y-5">
        <div className="om-panel p-5">
          <div className="om-kicker">Historical Recorder</div>
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <h1 className="om-title flex items-center gap-2 text-2xl">
                <Clock size={22} className="text-[color:var(--om-rust-400)]" /> Trace Timeline Explorer
              </h1>
              <p className="mt-1 max-w-3xl text-sm text-[color:var(--om-muted)]">
                Navigate the observed ecosystem as traces, relationships, sessions, and historical recorder events evolve over time.
              </p>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center text-xs sm:min-w-[320px]">
              <Metric label="Traces" value={traceList.length} />
              <Metric label="Timeline" value={timelineRows.length} />
              <Metric label="Events" value={eventList.length} />
            </div>
          </div>
        </div>

        {hasError && (
          <div className="om-alert-recovery flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <AlertTriangle size={18} className="mt-0.5 text-[color:var(--om-amber-500)]" />
              <div>
                <div className="text-sm font-semibold text-[color:var(--om-amber-300)]">History sources are partially unavailable</div>
                <p className="text-xs text-[color:var(--om-muted)]">OpenMesh kept the route mounted. Retry after the backend or database recovers.</p>
              </div>
            </div>
            <button type="button" className="om-button" onClick={refetchAll}>Retry</button>
          </div>
        )}

        {isLoading ? (
          <OpenMeshLoading label="Loading trace timeline" />
        ) : !hasContent ? (
          <OpenMeshEmptyState
            title="No timeline available"
            description="History will populate after OpenMesh observes traces, sessions, workflows, or graph relationships."
          >
            <div className="inline-flex items-center gap-2 rounded-[4px] border border-[color:var(--om-border)] bg-black/45 px-3 py-2 text-xs text-[color:var(--om-steel-300)]">
              <Radio size={13} /> Start observing an agent or run a showcase
            </div>
          </OpenMeshEmptyState>
        ) : (
          <div className="grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
            <section className="om-panel overflow-hidden">
              <div className="border-b border-[color:var(--om-border)] p-4">
                <div className="om-kicker">Trace Rail</div>
                <h2 className="text-sm font-semibold text-white">Recent Traces</h2>
              </div>
              <div className="max-h-[680px] overflow-auto p-3">
                {traceList.length === 0 ? (
                  <MiniEmpty label="No traces captured yet." />
                ) : (
                  <div className="space-y-2">
                    {traceList.map((trace) => (
                      <TraceCard key={trace.trace_id} trace={trace} />
                    ))}
                  </div>
                )}
              </div>
            </section>

            <div className="space-y-5">
              <ReplayPanel
                replay={replay}
                replayControl={replayControl}
                replaySpeed={replaySpeed}
                onPlay={() => setReplayControl("start")}
                onPause={() => setReplayControl("pause")}
                onStop={() => {
                  setReplayControl("stop");
                  setReplayPosition(0);
                }}
                onPrevious={() => {
                  const position = replay?.state?.position ?? replayPosition;
                  setReplayControl("previous");
                  setReplayPosition(Math.max(position, 0));
                }}
                onNext={() => {
                  const position = replay?.state?.position ?? replayPosition;
                  setReplayControl("step");
                  setReplayPosition(Math.max(position, 0));
                }}
                onSpeedChange={setReplaySpeed}
              />

              <section className="om-panel overflow-hidden">
                <div className="border-b border-[color:var(--om-border)] p-4">
                  <div className="om-kicker">Evolution Ledger</div>
                  <h2 className="text-sm font-semibold text-white">Timeline Changes</h2>
                </div>
                <div className="max-h-[430px] overflow-auto p-4">
                  {timelineRows.length === 0 ? (
                    <MiniEmpty label="No graph or workflow changes recorded yet." />
                  ) : (
                    <div className="relative">
                      <div className="absolute left-5 top-0 bottom-0 w-px bg-[color:var(--om-border)]" />
                      <div className="space-y-3">
                        {timelineRows.slice(0, 80).map((row, index) => (
                          <TimelineChange key={`${timelineLabel(row)}-${index}`} row={row} />
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </section>

              <section className="om-panel overflow-hidden">
                <div className="border-b border-[color:var(--om-border)] p-4">
                  <div className="om-kicker">Legacy Recorder</div>
                  <h2 className="text-sm font-semibold text-white">Simulation Events</h2>
                </div>
                <div className="max-h-[380px] overflow-auto p-4">
                  {eventList.length === 0 ? (
                    <MiniEmpty label="No simulation recorder events yet." />
                  ) : (
                    <div className="relative">
                      <div className="absolute left-5 top-0 bottom-0 w-px bg-[color:var(--om-border)]" />
                      <div className="space-y-4">
                        {eventList.map((evt: any) => (
                          <LegacyEvent key={evt.id || evt.event_id || `${evt.event_type}-${evt.occurred_at}`} evt={evt} />
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </section>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function ReplayPanel({
  replay,
  replayControl,
  replaySpeed,
  onPlay,
  onPause,
  onStop,
  onPrevious,
  onNext,
  onSpeedChange,
}: {
  replay?: OpenMeshReplay;
  replayControl: string;
  replaySpeed: number;
  onPlay: () => void;
  onPause: () => void;
  onStop: () => void;
  onPrevious: () => void;
  onNext: () => void;
  onSpeedChange: (speed: number) => void;
}) {
  const state = replay?.state || {};
  const metrics = replay?.metrics || {};
  const current = state.current_frame || undefined;
  const visible = replay?.visible_frames || [];
  const maxPosition = Math.max((state.frame_count || 0) - 1, 0);

  return (
    <section className="om-panel overflow-hidden">
      <div className="border-b border-[color:var(--om-border)] p-4">
        <div className="om-kicker">Time Travel Console</div>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <h2 className="text-sm font-semibold text-white">Workflow Replay</h2>
          <div className="flex flex-wrap items-center gap-2">
            <ReplayButton label="Previous" onClick={onPrevious}><SkipBack size={14} /></ReplayButton>
            {replayControl === "start" ? (
              <ReplayButton label="Pause" onClick={onPause}><Pause size={14} /></ReplayButton>
            ) : (
              <ReplayButton label="Play" onClick={onPlay}><Play size={14} /></ReplayButton>
            )}
            <ReplayButton label="Next" onClick={onNext}><SkipForward size={14} /></ReplayButton>
            <button type="button" className="om-button" onClick={onStop}>Stop</button>
            <select
              className="input h-9 w-[88px] text-xs"
              value={replaySpeed}
              onChange={(event) => onSpeedChange(Number(event.target.value))}
              aria-label="Replay speed"
            >
              <option value={0.5}>0.5x</option>
              <option value={1}>1x</option>
              <option value={2}>2x</option>
              <option value={4}>4x</option>
            </select>
          </div>
        </div>
      </div>

      <div className="grid gap-4 p-4 lg:grid-cols-[1.1fr_.9fr]">
        <div className="rounded-[6px] border border-[color:var(--om-border)] bg-black/30 p-4">
          <div className="flex items-center justify-between gap-3">
            <div className="om-kicker">Current Frame</div>
            <span className="font-mono text-xs text-[color:var(--om-muted)]">
              {state.position ?? "-"} / {maxPosition}
            </span>
          </div>
          {current ? (
            <div className="mt-3">
              <div className="text-sm font-semibold text-white">{replayFrameTitle(current)}</div>
              <div className="mt-1 font-mono text-xs text-[color:var(--om-muted)]">{current.timestamp || "time unknown"}</div>
              <p className="mt-3 text-sm leading-6 text-[color:var(--om-steel-300)]">{current.description || "OpenMesh replay frame"}</p>
            </div>
          ) : (
            <MiniEmpty label="Replay is waiting for timeline events." />
          )}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Metric label="Events" value={metrics.events_replayed || 0} />
          <Metric label="Mutations" value={metrics.graph_mutations || 0} />
          <Metric label="Duration" value={formatSeconds(metrics.duration)} />
          <Metric label="Workflow" value={formatSeconds(metrics.workflow_duration)} />
        </div>
      </div>

      <div className="border-t border-[color:var(--om-border)] p-4">
        <div className="mb-3 flex items-center justify-between">
          <div className="om-kicker">Visible Evolution</div>
          <span className="text-xs text-[color:var(--om-muted)]">{visible.length} frames replayed</span>
        </div>
        {visible.length === 0 ? (
          <MiniEmpty label="No replay frames are visible at the current position." />
        ) : (
          <div className="max-h-[220px] overflow-auto space-y-2">
            {visible.slice(-10).map((frame) => (
              <div key={`${frame.frame_index}-${frame.action}`} className="flex items-center gap-3 rounded-[4px] border border-[color:var(--om-border)] bg-black/25 px-3 py-2">
                <span className="font-mono text-[10px] text-[color:var(--om-rust-300)]">#{frame.frame_index ?? "-"}</span>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-xs font-semibold text-[color:var(--om-text)]">{replayFrameTitle(frame)}</div>
                  <div className="truncate text-[11px] text-[color:var(--om-muted)]">{frame.description || "-"}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function ReplayButton({ label, onClick, children }: { label: string; onClick: () => void; children: ReactNode }) {
  return (
    <button type="button" className="om-icon-button" onClick={onClick} aria-label={label} title={label}>
      {children}
    </button>
  );
}

function Metric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-[5px] border border-[color:var(--om-border)] bg-black/35 px-3 py-2">
      <div className="text-lg font-semibold text-white">{value}</div>
      <div className="om-kicker text-[10px]">{label}</div>
    </div>
  );
}

function TraceCard({ trace }: { trace: OpenMeshTraceSummary }) {
  return (
    <div className="rounded-[6px] border border-[color:var(--om-border)] bg-black/35 p-3 transition-colors hover:border-[color:var(--om-border-strong)]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate font-mono text-xs text-[color:var(--om-steel-100)]">{trace.trace_id || "trace unknown"}</div>
          <div className="mt-1 flex flex-wrap gap-2 text-[10px] uppercase tracking-[.14em] text-[color:var(--om-muted)]">
            <span>{trace.event_count || 0} events</span>
            <span>{trace.started_at ? timeAgo(trace.started_at) : "time unknown"}</span>
          </div>
        </div>
        <StatusBadge status={trace.status} />
      </div>
      {(trace.agents?.length || trace.tools?.length) ? (
        <div className="mt-2 text-xs text-[color:var(--om-muted)]">
          {[...(trace.agents || []), ...(trace.tools || [])].slice(0, 3).join(" -> ")}
        </div>
      ) : null}
    </div>
  );
}

function TimelineChange({ row }: { row: Record<string, unknown> }) {
  const label = timelineLabel(row);
  const timestamp = rowTime(row);

  return (
    <div className="relative flex gap-4">
      <div className="z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-[6px] border border-[color:var(--om-rust-500)]/45 bg-black/55 text-[color:var(--om-rust-300)]">
        <GitBranch size={16} />
      </div>
      <div className="card mb-0 flex-1 p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-white">{label}</p>
            <p className="mt-1 font-mono text-xs text-[color:var(--om-muted)]">{rowDescription(row)}</p>
          </div>
          <span className="shrink-0 text-xs text-[color:var(--om-dim)]">{timestamp ? timeAgo(timestamp) : "time unknown"}</span>
        </div>
      </div>
    </div>
  );
}

function LegacyEvent({ evt }: { evt: any }) {
  const Icon = EVENT_ICONS[evt.event_type] || Clock;
  const colorClass = EVENT_COLORS[evt.event_type] || "text-[color:var(--om-steel-300)] bg-black/40 border-[color:var(--om-border)]";

  return (
    <div className="relative flex gap-4">
      <div className={`z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-[6px] border ${colorClass}`}>
        <Icon size={16} />
      </div>
      <div className="card mb-0 flex-1 p-4">
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="text-sm font-medium text-white">{brandText(evt.title || evt.event_type, "Recorded event")}</p>
            {evt.description && (
              <p className="mt-0.5 text-xs leading-relaxed text-[color:var(--om-muted)]">{brandText(evt.description).slice(0, 150)}</p>
            )}
          </div>
          <span className="shrink-0 text-xs text-[color:var(--om-dim)]">{evt.occurred_at ? timeAgo(evt.occurred_at) : "time unknown"}</span>
        </div>
        <div className="mt-2 flex items-center gap-2">
          <span className={`rounded-full border px-2 py-0.5 text-xs capitalize ${colorClass}`}>
            {String(evt.event_type || "event").replace("_", " ")}
          </span>
          {evt.agent_ids?.length > 0 && (
            <span className="flex items-center gap-1 text-xs text-[color:var(--om-dim)]">
              <Users size={10} /> {evt.agent_ids.length} agent{evt.agent_ids.length > 1 ? "s" : ""}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status?: string }) {
  const normalized = String(status || "unknown").toLowerCase();
  return (
    <span
      className={cn(
        "rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[.12em]",
        normalized.includes("fail") || normalized.includes("error")
          ? "border-[color:var(--om-red-500)]/50 text-[color:var(--om-red-500)]"
          : normalized.includes("active") || normalized.includes("running")
            ? "border-[color:var(--om-green-500)]/45 text-[color:var(--om-green-500)]"
            : "border-[color:var(--om-border)] text-[color:var(--om-steel-300)]",
      )}
    >
      {normalized}
    </span>
  );
}

function MiniEmpty({ label }: { label: string }) {
  return <div className="rounded-[6px] border border-dashed border-[color:var(--om-border)] bg-black/20 p-4 text-sm text-[color:var(--om-muted)]">{label}</div>;
}

function collectTimelineRows(timeline?: OpenMeshTimeline) {
  const rows = [
    ...(timeline?.relationship_changes || []),
    ...(timeline?.workflow_changes || []),
    ...(timeline?.capability_changes || []),
    ...(timeline?.mcp_changes || []),
    ...(timeline?.session_history || []),
    ...(timeline?.snapshot_history || []),
    ...(timeline?.timeline || []),
  ];

  return rows
    .filter(Boolean)
    .sort((a, b) => new Date(rowTime(b) || 0).getTime() - new Date(rowTime(a) || 0).getTime());
}

function timelineLabel(row: Record<string, unknown>) {
  return brandText(String(row.label || row.event_type || row.change_type || row.type || row.relationship_type || row.scope || "Timeline change"));
}

function rowDescription(row: Record<string, unknown>) {
  const parts = [
    row.source || row.source_id || row.workflow_id || row.node_id,
    row.relationship_type || row.action || row.status,
    row.target || row.target_id || row.trace_id || row.session_id,
  ].filter(Boolean);
  return parts.length ? parts.map(String).join(" -> ") : "OpenMesh historical observation";
}

function rowTime(row: Record<string, unknown>) {
  return String(row.timestamp || row.created_at || row.started_at || row.first_seen || row.last_seen || "");
}

function replayFrameTitle(frame: OpenMeshReplayFrame) {
  return brandText(String(frame.action || frame.event_type || frame.category || "Replay frame"));
}

function formatSeconds(value?: number | null) {
  if (value === null || value === undefined) return "-";
  return `${Number(value).toFixed(value >= 10 ? 0 : 1)}s`;
}
