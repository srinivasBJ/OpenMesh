import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, KeyRound, Loader2, Plug, X, XCircle } from "lucide-react";
import { providersApi, type DiscoveredModel } from "@/api";
import { cn } from "@/lib/utils";

const CLOUD_PROVIDERS = [
  { id: "anthropic", label: "Anthropic" },
  { id: "openai", label: "OpenAI" },
  { id: "openrouter", label: "OpenRouter" },
];

type TestState =
  | { kind: "idle" }
  | { kind: "busy" }
  | { kind: "ok"; message: string }
  | { kind: "fail"; message: string };

/**
 * Provider → Model manager. Paste a key once: it is validated against the
 * provider's live API, stored encrypted server-side, and the provider's
 * model catalog is discovered (never hardcoded). Selecting a model makes it
 * the active brain for agent sessions — no restart required.
 */
export default function ProviderManagerModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [provider, setProvider] = useState("anthropic");
  const [apiKey, setApiKey] = useState("");
  const [state, setState] = useState<TestState>({ kind: "idle" });
  const [models, setModels] = useState<DiscoveredModel[]>([]);

  const { data: status } = useQuery({ queryKey: ["providers"], queryFn: providersApi.list });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["providers"] });
    qc.invalidateQueries({ queryKey: ["provider-settings"] });
    qc.invalidateQueries({ queryKey: ["live-status"] });
  };

  const connect = useMutation({
    mutationFn: () => providersApi.connect(provider, { api_key: apiKey }),
    onMutate: () => setState({ kind: "busy" }),
    onSuccess: (result) => {
      setModels(result.models);
      setState({ kind: "ok", message: `Connected — ${result.models.length} models discovered` });
      setApiKey("");
      invalidate();
    },
    onError: (error: any) =>
      setState({ kind: "fail", message: error?.response?.data?.detail || "Connection failed" }),
  });

  const selectModel = useMutation({
    mutationFn: (model: string) => providersApi.select({ provider, model }),
    onSettled: invalidate,
  });

  const loadModels = useMutation({
    mutationFn: () => providersApi.models(provider),
    onMutate: () => setState({ kind: "busy" }),
    onSuccess: (discovered) => {
      setModels(discovered);
      setState({ kind: "ok", message: `${discovered.length} models discovered` });
    },
    onError: (error: any) =>
      setState({ kind: "fail", message: error?.response?.data?.detail || "Model discovery failed" }),
  });

  const entries = status?.providers.filter((p) => !p.is_local) ?? [];
  const selected = status?.selected ?? null;
  const activeEntry = entries.find((p) => p.provider === provider);
  const busy = connect.isPending || loadModels.isPending;

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 p-6 backdrop-blur-sm">
      <div className="om-card flex max-h-[90vh] w-full max-w-2xl flex-col p-7">
        <div className="flex items-start justify-between">
          <div>
            <div className="om-kicker">Provider Manager</div>
            <h1 className="text-2xl font-black text-[color:var(--om-text)]">Connect AI Provider</h1>
            <p className="mt-1 text-sm text-[color:var(--om-muted)]">
              Provider → Model → Agent. Keys are validated live and stored encrypted on this machine.
            </p>
          </div>
          <button type="button" className="om-button-ghost h-9 w-9 p-0" aria-label="Close" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <div className="mt-5 grid gap-2 sm:grid-cols-3">
          {CLOUD_PROVIDERS.map((p) => {
            const entry = entries.find((e) => e.provider === p.id);
            return (
              <button
                key={p.id}
                type="button"
                onClick={() => {
                  setProvider(p.id);
                  setModels([]);
                  setState({ kind: "idle" });
                }}
                className={cn(
                  "rounded-[4px] border px-3 py-2 text-left text-sm font-semibold transition-colors",
                  provider === p.id
                    ? "border-[color:var(--om-border-strong)] bg-[rgba(90,36,16,.42)] text-[color:var(--om-rust-300)]"
                    : "border-[color:var(--om-border)] text-[color:var(--om-steel-400)] hover:text-[color:var(--om-text)]",
                )}
              >
                <div className="flex items-center justify-between">
                  {p.label}
                  {entry?.configured ? <CheckCircle2 size={14} className="text-[color:var(--om-green-500)]" /> : null}
                </div>
                <div className="mt-1 text-xs font-normal text-[color:var(--om-dim)]">
                  {entry?.configured
                    ? `${entry.masked_key ?? "key set"}${entry.selected ? " · active" : ""}`
                    : "not connected"}
                </div>
              </button>
            );
          })}
        </div>

        <form
          className="mt-5 flex gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            if (apiKey.trim()) connect.mutate();
          }}
        >
          <div className="relative flex-1">
            <KeyRound size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[color:var(--om-dim)]" />
            <input
              type="password"
              autoComplete="off"
              spellCheck={false}
              className="om-input w-full pl-9"
              placeholder={activeEntry?.configured ? "Replace API key…" : "Paste API key…"}
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
            />
          </div>
          <button type="submit" className="om-button px-4" disabled={!apiKey.trim() || busy}>
            {connect.isPending ? <Loader2 size={15} className="animate-spin" /> : <Plug size={15} />}
            Connect
          </button>
          {activeEntry?.configured ? (
            <button type="button" className="om-button-ghost px-4" disabled={busy} onClick={() => loadModels.mutate()}>
              {loadModels.isPending ? <Loader2 size={15} className="animate-spin" /> : null}
              Discover Models
            </button>
          ) : null}
        </form>

        {state.kind === "ok" || state.kind === "fail" ? (
          <div
            className={cn(
              "mt-3 flex items-start gap-2 rounded-[4px] border px-3 py-2 text-sm",
              state.kind === "ok"
                ? "border-[color:var(--om-green-500)] text-[color:var(--om-green-500)]"
                : "border-red-700 text-red-400",
            )}
          >
            {state.kind === "ok" ? <CheckCircle2 size={16} className="mt-0.5 shrink-0" /> : <XCircle size={16} className="mt-0.5 shrink-0" />}
            <span className="break-words">{state.message}</span>
          </div>
        ) : null}

        {models.length > 0 ? (
          <div className="mt-4 min-h-0 flex-1 overflow-y-auto rounded-[4px] border border-[color:var(--om-border)] p-2">
            <div className="om-kicker px-2 pb-2">Discovered models — click to activate</div>
            <div className="grid gap-1 sm:grid-cols-2">
              {models.map((model) => {
                const active = selected?.provider === provider && selected?.model === model.model;
                return (
                  <button
                    key={model.model}
                    type="button"
                    disabled={selectModel.isPending}
                    onClick={() => selectModel.mutate(model.model)}
                    className={cn(
                      "truncate rounded-[3px] border px-2 py-1.5 text-left font-mono text-xs transition-colors",
                      active
                        ? "border-[color:var(--om-green-500)] text-[color:var(--om-green-500)]"
                        : "border-transparent text-[color:var(--om-muted)] hover:border-[color:var(--om-border)] hover:text-[color:var(--om-text)]",
                    )}
                    title={model.model}
                  >
                    {active ? "● " : ""}{model.model}
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}

        {selected?.provider ? (
          <div className="mt-4 text-sm text-[color:var(--om-muted)]">
            Active: <span className="text-[color:var(--om-text)]">{selected.provider}</span>
            {selected.model ? <span className="font-mono"> · {selected.model}</span> : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}
