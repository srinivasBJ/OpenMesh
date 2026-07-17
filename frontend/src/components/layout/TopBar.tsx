import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, AlertTriangle, Cpu, Loader2, Pause, Play, Square, Users } from "lucide-react";
import { controlApi, sessionApi } from "@/api";
import { useWSStore } from "@/store/wsStore";
import { useWorkspaceStore } from "@/store/workspaceStore";
import ProviderManagerModal from "@/components/providers/ProviderManagerModal";
import Modal from "@/components/shared/Modal";
import { apiErrorMessage, refreshAppState } from "@/lib/appState";
import { cn } from "@/lib/utils";
import toast from "react-hot-toast";

/**
 * Live status bar: backend link, active provider/model, events per second,
 * agent count, and agent session controls (start / pause / resume /
 * terminate). Terminate always returns to an idle state — no page traps.
 */
export default function TopBar() {
  const qc = useQueryClient();
  const { connected } = useWSStore();
  const activeWorkspaceId = useWorkspaceStore((s) => s.activeWorkspaceId);
  const [providersOpen, setProvidersOpen] = useState(false);
  const [confirmTerminate, setConfirmTerminate] = useState(false);

  const { data: status } = useQuery({
    queryKey: ["live-status"],
    queryFn: controlApi.liveStatus,
    refetchInterval: 5000,
    retry: false,
  });

  // Every session action refreshes all live views — no browser refresh.
  const invalidate = () => refreshAppState(qc);
  const start = useMutation({
    mutationFn: () => sessionApi.start(activeWorkspaceId ?? undefined),
    onSuccess: () => toast.success("Agent session started."),
    onError: (error) => toast.error(apiErrorMessage(error, "Starting the session failed")),
    onSettled: invalidate,
  });
  const pause = useMutation({
    mutationFn: sessionApi.pause,
    onError: (error) => toast.error(apiErrorMessage(error, "Pausing failed")),
    onSettled: invalidate,
  });
  const resume = useMutation({
    mutationFn: sessionApi.resume,
    onError: (error) => toast.error(apiErrorMessage(error, "Resuming failed")),
    onSettled: invalidate,
  });
  const terminate = useMutation({
    mutationFn: sessionApi.terminate,
    onSuccess: () => {
      setConfirmTerminate(false);
      toast.success("Session terminated. No active agents.");
    },
    onError: (error) => toast.error(apiErrorMessage(error, "Terminating failed")),
    onSettled: invalidate,
  });

  const backendUp = connected || Boolean(status);
  const provider = status?.provider;
  const runner = status?.runner;
  const running = runner?.running ?? false;
  const paused = (runner as { paused?: boolean } | undefined)?.paused ?? false;
  const busy = start.isPending || pause.isPending || resume.isPending || terminate.isPending;

  return (
    <header className="om-topbar sticky top-0 z-30 flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-[color:var(--om-border)] bg-black/60 px-6 py-3 backdrop-blur">
      <Stat label="Backend">
        <span className={cn("om-status-dot", backendUp ? "om-status-active animate-pulse" : "bg-[color:var(--om-steel-700)]")} />
        <span className={backendUp ? "text-[color:var(--om-green-500)]" : "text-[color:var(--om-dim)]"}>
          {backendUp ? "Connected" : "Offline"}
        </span>
      </Stat>

      <button type="button" className="group" onClick={() => setProvidersOpen(true)} title="Manage providers">
        <Stat label="Provider" icon={<Cpu size={13} />}>
          {provider?.configured ? (
            <span className="text-[color:var(--om-text)] group-hover:text-[color:var(--om-rust-300)]">
              {provider.name}
              {provider.model ? <span className="text-[color:var(--om-muted)]"> · {provider.model}</span> : null}
            </span>
          ) : (
            <span className="text-[color:var(--om-dim)] group-hover:text-[color:var(--om-rust-300)]">Connect…</span>
          )}
        </Stat>
      </button>

      <Stat label="Events/sec" icon={<Activity size={13} />}>
        <span className="font-mono text-[color:var(--om-text)]">{(status?.events_per_second ?? 0).toFixed(2)}</span>
      </Stat>

      <Stat label="Agents" icon={<Users size={13} />}>
        <span className="font-mono text-[color:var(--om-text)]">{status?.agents.active ?? 0}</span>
        <span className={cn("text-xs", running ? (paused ? "text-[color:var(--om-rust-300)]" : "text-[color:var(--om-green-500)]") : "text-[color:var(--om-dim)]")}>
          {running ? (paused ? "paused" : "running") : "idle"}
        </span>
      </Stat>

      <div className="ml-auto flex items-center gap-2">
        {!running ? (
          <button type="button" className="om-button h-9 px-4 text-sm" disabled={busy} onClick={() => start.mutate()}>
            {start.isPending ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            Start Session
          </button>
        ) : (
          <>
            {paused ? (
              <button type="button" className="om-button h-9 px-3 text-sm" disabled={busy} onClick={() => resume.mutate()}>
                <Play size={14} /> Resume
              </button>
            ) : (
              <button type="button" className="om-button-ghost h-9 px-3 text-sm" disabled={busy} onClick={() => pause.mutate()}>
                <Pause size={14} /> Pause
              </button>
            )}
            <button type="button" className="om-button-ghost h-9 px-3 text-sm" disabled={busy} onClick={() => setConfirmTerminate(true)}>
              <Square size={14} />
              Terminate
            </button>
          </>
        )}
      </div>

      {providersOpen ? <ProviderManagerModal onClose={() => setProvidersOpen(false)} /> : null}
      {confirmTerminate ? (
        <Modal onClose={() => setConfirmTerminate(false)} maxWidth="max-w-md" showClose={false} aria-label="Confirm session termination">
          <div className="text-center">
            <AlertTriangle size={26} className="mx-auto text-[color:var(--om-rust-300)]" />
            <h2 className="mt-3 text-xl font-bold text-[color:var(--om-text)]">Terminate this agent session?</h2>
            <p className="mt-2 text-sm text-[color:var(--om-muted)]">
              The tick loop stops and you return to the normal workspace view. Agents and their history are kept.
            </p>
            <div className="mt-5 flex justify-center gap-3">
              <button type="button" className="om-button-ghost px-5" disabled={terminate.isPending} onClick={() => setConfirmTerminate(false)}>
                Cancel
              </button>
              <button type="button" className="om-button px-5" disabled={terminate.isPending} onClick={() => terminate.mutate()}>
                {terminate.isPending ? <Loader2 size={14} className="animate-spin" /> : <Square size={14} />}
                Terminate
              </button>
            </div>
          </div>
        </Modal>
      ) : null}
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
