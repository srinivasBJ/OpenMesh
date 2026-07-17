import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Cpu, Loader2, Play, Square, Users } from "lucide-react";
import { controlApi } from "@/api";
import { useWSStore } from "@/store/wsStore";
import { cn } from "@/lib/utils";

/**
 * Live status bar: backend link, active provider/model, events per second,
 * running agent count, and the Start/Stop agent control.
 */
export default function TopBar() {
  const qc = useQueryClient();
  const { connected } = useWSStore();

  const { data: status } = useQuery({
    queryKey: ["live-status"],
    queryFn: controlApi.liveStatus,
    refetchInterval: 5000,
    retry: false,
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["live-status"] });
  const start = useMutation({ mutationFn: controlApi.startAgents, onSettled: invalidate });
  const stop = useMutation({ mutationFn: controlApi.stopAgents, onSettled: invalidate });

  const backendUp = connected || Boolean(status);
  const provider = status?.provider;
  const running = status?.agents.running ?? false;
  const busy = start.isPending || stop.isPending;

  return (
    <header className="om-topbar sticky top-0 z-30 flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-[color:var(--om-border)] bg-black/60 px-6 py-3 backdrop-blur">
      <Stat label="Backend">
        <span className={cn("om-status-dot", backendUp ? "om-status-active animate-pulse" : "bg-[color:var(--om-steel-700)]")} />
        <span className={backendUp ? "text-[color:var(--om-green-500)]" : "text-[color:var(--om-dim)]"}>
          {backendUp ? "Connected" : "Offline"}
        </span>
      </Stat>

      <Stat label="Provider" icon={<Cpu size={13} />}>
        {provider?.configured ? (
          <span className="text-[color:var(--om-text)]">
            {provider.name}
            {provider.model ? <span className="text-[color:var(--om-muted)]"> · {provider.model}</span> : null}
          </span>
        ) : (
          <span className="text-[color:var(--om-dim)]">Not configured</span>
        )}
      </Stat>

      <Stat label="Events/sec" icon={<Activity size={13} />}>
        <span className="font-mono text-[color:var(--om-text)]">{(status?.events_per_second ?? 0).toFixed(2)}</span>
      </Stat>

      <Stat label="Agents" icon={<Users size={13} />}>
        <span className="font-mono text-[color:var(--om-text)]">{status?.agents.active ?? 0}</span>
        <span className={cn("text-xs", running ? "text-[color:var(--om-green-500)]" : "text-[color:var(--om-dim)]")}>
          {running ? "running" : "idle"}
        </span>
      </Stat>

      <div className="ml-auto">
        {provider?.configured ? (
          <button
            type="button"
            className={cn("om-button h-9 px-4 text-sm", running && "om-button-ghost")}
            disabled={busy}
            onClick={() => (running ? stop.mutate() : start.mutate())}
          >
            {busy ? <Loader2 size={14} className="animate-spin" /> : running ? <Square size={14} /> : <Play size={14} />}
            {running ? "Stop Agent" : "Start Agent"}
          </button>
        ) : null}
      </div>
    </header>
  );
}

function Stat({ label, icon, children }: { label: string; icon?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="om-kicker flex items-center gap-1.5">{icon}{label}</span>
      <span className="flex items-center gap-1.5">{children}</span>
    </div>
  );
}
