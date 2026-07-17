import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Loader2, Play, Square, Trash2 } from "lucide-react";
import { demoApi } from "@/api";
import Modal from "@/components/shared/Modal";
import { apiErrorMessage, refreshAppState } from "@/lib/appState";
import { useWorkspaceStore } from "@/store/workspaceStore";
import toast from "react-hot-toast";

/**
 * "Simulation Mode" banner shown while the temporary demo workspace exists.
 * Stop pauses the simulation but keeps data; Terminate (with confirmation)
 * deletes every demo trace, event, and agent, returning to first-launch.
 */
export default function DemoBanner() {
  const qc = useQueryClient();
  const { activeWorkspaceId, setActiveWorkspace } = useWorkspaceStore();
  const [confirming, setConfirming] = useState(false);

  const { data: demo } = useQuery({
    queryKey: ["demo-status"],
    queryFn: demoApi.status,
    refetchInterval: 5000,
    retry: false,
  });

  const invalidateAll = () => refreshAppState(qc);

  const stop = useMutation({
    mutationFn: demoApi.stop,
    onSettled: invalidateAll,
    onError: (error) => toast.error(apiErrorMessage(error, "Stopping the demo failed")),
  });
  const resume = useMutation({
    mutationFn: demoApi.start,
    onSettled: invalidateAll,
    onError: (error) => toast.error(apiErrorMessage(error, "Resuming the demo failed")),
  });
  const terminate = useMutation({
    mutationFn: demoApi.terminate,
    onSuccess: () => {
      setConfirming(false);
      if (demo?.workspace && activeWorkspaceId === demo.workspace.id) {
        setActiveWorkspace(null);
      }
      invalidateAll();
      toast.success("Demo terminated — all demo data removed.");
    },
    onError: (error) => toast.error(apiErrorMessage(error, "Terminating the demo failed")),
  });

  if (!demo?.active) return null;
  const busy = stop.isPending || resume.isPending || terminate.isPending;

  return (
    <>
      <div className="flex flex-wrap items-center gap-3 border-b border-[color:var(--om-border-strong)] bg-[rgba(90,36,16,.35)] px-6 py-2 text-sm">
        <AlertTriangle size={15} className="text-[color:var(--om-rust-300)]" />
        <span className="font-bold uppercase tracking-[.12em] text-[color:var(--om-rust-300)]">Simulation Mode</span>
        <span className="text-[color:var(--om-muted)]">
          {demo.workspace?.name} · {demo.agents.map((a) => a.name).join(", ")}
          {demo.running ? " · running" : " · stopped"}
        </span>
        <div className="ml-auto flex gap-2">
          {demo.running ? (
            <button type="button" className="om-button-ghost h-8 px-3 text-xs" disabled={busy} onClick={() => stop.mutate()}>
              <Square size={13} /> Stop Demo
            </button>
          ) : (
            <button type="button" className="om-button-ghost h-8 px-3 text-xs" disabled={busy} onClick={() => resume.mutate()}>
              <Play size={13} /> Resume Demo
            </button>
          )}
          <button type="button" className="om-button h-8 px-3 text-xs" disabled={busy} onClick={() => setConfirming(true)}>
            <Trash2 size={13} /> Terminate Demo
          </button>
        </div>
      </div>

      {confirming ? (
        <Modal onClose={() => setConfirming(false)} maxWidth="max-w-md" showClose={false} aria-label="Confirm demo termination">
          <div className="text-center">
            <AlertTriangle size={28} className="mx-auto text-[color:var(--om-rust-300)]" />
            <h2 className="mt-3 text-xl font-bold text-[color:var(--om-text)]">
              Delete demo traces, events and agents?
            </h2>
            <p className="mt-2 text-sm text-[color:var(--om-muted)]">
              This removes the demo workspace and everything it produced, returning OpenMesh to a clean first-launch state.
            </p>
            <div className="mt-5 flex justify-center gap-3">
              <button type="button" className="om-button-ghost px-5" disabled={terminate.isPending} onClick={() => setConfirming(false)}>
                Cancel
              </button>
              <button type="button" className="om-button px-5" disabled={terminate.isPending} onClick={() => terminate.mutate()}>
                {terminate.isPending ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                Delete demo data
              </button>
            </div>
          </div>
        </Modal>
      ) : null}
    </>
  );
}
