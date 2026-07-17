import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, KeyRound, Loader2, Plug, Search, Unplug, XCircle } from "lucide-react";
import { providersApi, type DiscoveredModel } from "@/api";
import Modal from "@/components/shared/Modal";
import { apiErrorMessage, refreshAppState } from "@/lib/appState";
import { cn } from "@/lib/utils";
import toast from "react-hot-toast";

const CLOUD_PROVIDERS = [
  { id: "anthropic", label: "Anthropic" },
  { id: "openai", label: "OpenAI" },
  { id: "openrouter", label: "OpenRouter" },
];

const CATEGORIES = [
  { id: "all", label: "Recommended" },
  { id: "coding", label: "Coding" },
  { id: "reasoning", label: "Reasoning" },
  { id: "fast", label: "Fast / Cheap" },
] as const;

type Feedback = { kind: "ok" | "fail"; message: string } | null;

/**
 * Provider → Model manager. Connect validates the key against the
 * provider's live API and discovers its model catalog. The default view is
 * a curated top-25 (categorized); search and "Show all models" cover the
 * long tail. Picking a model activates it and closes the modal.
 */
export default function ProviderManagerModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [provider, setProvider] = useState("anthropic");
  const [apiKey, setApiKey] = useState("");
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [category, setCategory] = useState<(typeof CATEGORIES)[number]["id"]>("all");
  const [search, setSearch] = useState("");
  const [showAll, setShowAll] = useState(false);

  const { data: status } = useQuery({ queryKey: ["providers"], queryFn: providersApi.list });
  const entries = status?.providers.filter((p) => !p.is_local) ?? [];
  const activeEntry = entries.find((p) => p.provider === provider);
  const selected = status?.selected ?? null;

  // Model discovery for the focused provider (only once connected).
  const { data: discovery, isFetching: discovering, error: discoveryError } = useQuery({
    queryKey: ["provider-models", provider],
    queryFn: () => providersApi.models(provider),
    enabled: Boolean(activeEntry?.configured),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const connect = useMutation({
    mutationFn: () => providersApi.connect(provider, { api_key: apiKey }),
    onMutate: () => setFeedback(null),
    onSuccess: (result) => {
      setFeedback({ kind: "ok", message: `Connected — ${result.models.length} models discovered. Pick one below.` });
      setApiKey("");
      qc.setQueryData(["provider-models", provider], {
        provider,
        models: result.models,
        curated: result.curated ?? [],
      });
      refreshAppState(qc);
    },
    onError: (error) =>
      setFeedback({ kind: "fail", message: apiErrorMessage(error, "Authentication failed. Check your API key.") }),
  });

  const selectModel = useMutation({
    mutationFn: (model: string) => providersApi.select({ provider, model }),
    onSuccess: (_, model) => {
      refreshAppState(qc);
      toast.success(`Active model: ${model}`);
      onClose(); // model picked → picker closes, dashboard reflects it
    },
    onError: (error) =>
      setFeedback({ kind: "fail", message: apiErrorMessage(error, "Model no longer available.") }),
  });

  const disconnect = useMutation({
    mutationFn: () => providersApi.disconnect(provider),
    onSuccess: () => {
      setFeedback({ kind: "ok", message: `${activeEntry?.name ?? provider} disconnected.` });
      qc.removeQueries({ queryKey: ["provider-models", provider] });
      refreshAppState(qc);
    },
    onError: (error) =>
      setFeedback({ kind: "fail", message: apiErrorMessage(error, "Disconnecting failed.") }),
  });

  const visibleModels = useMemo(() => {
    if (!discovery) return [];
    const needle = search.trim().toLowerCase();
    if (needle) {
      return discovery.models.filter((m) => m.model.toLowerCase().includes(needle)).slice(0, 100);
    }
    let pool: DiscoveredModel[] = showAll ? discovery.models : discovery.curated;
    if (category !== "all") pool = pool.filter((m) => m.category === category);
    return pool;
  }, [discovery, search, showAll, category]);

  const busy = connect.isPending || disconnect.isPending || selectModel.isPending;

  return (
    <Modal onClose={onClose} maxWidth="max-w-2xl" aria-label="Provider manager">
      <div className="pr-10">
        <div className="om-kicker">Provider Manager</div>
        <h1 className="text-2xl font-black text-[color:var(--om-text)]">Connect AI Provider</h1>
        <p className="mt-1 text-sm text-[color:var(--om-muted)]">
          Provider → Model → Agent. Keys are validated live and stored encrypted on this machine.
        </p>
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
                setFeedback(null);
                setSearch("");
                setCategory("all");
                setShowAll(false);
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
              <div className="mt-1 truncate text-xs font-normal text-[color:var(--om-dim)]">
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
          <button
            type="button"
            className="om-button-ghost px-3"
            title={`Disconnect ${activeEntry.name}`}
            disabled={busy}
            onClick={() => disconnect.mutate()}
          >
            {disconnect.isPending ? <Loader2 size={15} className="animate-spin" /> : <Unplug size={15} />}
          </button>
        ) : null}
      </form>

      {feedback ? (
        <div
          className={cn(
            "mt-3 flex items-start gap-2 rounded-[4px] border px-3 py-2 text-sm",
            feedback.kind === "ok"
              ? "border-[color:var(--om-green-500)] text-[color:var(--om-green-500)]"
              : "border-red-700 text-red-400",
          )}
        >
          {feedback.kind === "ok" ? <CheckCircle2 size={16} className="mt-0.5 shrink-0" /> : <XCircle size={16} className="mt-0.5 shrink-0" />}
          <span className="break-words">{feedback.message}</span>
        </div>
      ) : null}
      {discoveryError ? (
        <div className="mt-3 rounded-[4px] border border-red-700 px-3 py-2 text-sm text-red-400">
          {apiErrorMessage(discoveryError, "Unable to reach provider.")}
        </div>
      ) : null}

      {activeEntry?.configured ? (
        <div className="mt-4">
          <div className="flex flex-wrap items-center gap-2">
            {CATEGORIES.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => {
                  setCategory(c.id);
                  setSearch("");
                }}
                className={cn(
                  "om-chip px-3 py-1 text-xs",
                  category === c.id && !search && "om-chip-active",
                )}
              >
                {c.label}
              </button>
            ))}
            <div className="relative ml-auto">
              <Search size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[color:var(--om-dim)]" />
              <input
                className="om-input h-8 w-44 pl-8 text-xs"
                placeholder="Search models…"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </div>
          </div>

          <div className="mt-3 max-h-64 overflow-y-auto rounded-[4px] border border-[color:var(--om-border)] p-2">
            {discovering && !discovery ? (
              <div className="flex items-center justify-center gap-2 p-4 text-sm text-[color:var(--om-muted)]">
                <Loader2 size={14} className="animate-spin" /> Discovering models…
              </div>
            ) : visibleModels.length === 0 ? (
              <div className="p-4 text-center text-sm text-[color:var(--om-dim)]">
                {search ? "No models match your search." : "No models in this category."}
              </div>
            ) : (
              <div className="grid gap-1 sm:grid-cols-2">
                {visibleModels.map((model) => {
                  const active = selected?.provider === provider && selected?.model === model.model;
                  return (
                    <button
                      key={model.model}
                      type="button"
                      disabled={selectModel.isPending}
                      onClick={() => selectModel.mutate(model.model)}
                      className={cn(
                        "flex items-center gap-2 rounded-[3px] border px-2 py-1.5 text-left font-mono text-xs transition-colors",
                        active
                          ? "border-[color:var(--om-green-500)] text-[color:var(--om-green-500)]"
                          : "border-transparent text-[color:var(--om-muted)] hover:border-[color:var(--om-border)] hover:text-[color:var(--om-text)]",
                      )}
                      title={model.model}
                    >
                      <span className="min-w-0 flex-1 truncate">{active ? "● " : ""}{model.model}</span>
                      {model.category && model.category !== "general" ? (
                        <span className="shrink-0 text-[10px] uppercase tracking-wide text-[color:var(--om-dim)]">{model.category}</span>
                      ) : null}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {!search ? (
            <button
              type="button"
              className="mt-2 text-xs text-[color:var(--om-dim)] underline-offset-2 hover:text-[color:var(--om-rust-300)] hover:underline"
              onClick={() => setShowAll((value) => !value)}
            >
              {showAll
                ? "Show recommended models"
                : `Show all models${discovery ? ` (${discovery.models.length})` : ""}`}
            </button>
          ) : null}
        </div>
      ) : null}

      {selected?.provider ? (
        <div className="mt-4 text-sm text-[color:var(--om-muted)]">
          Active: <span className="text-[color:var(--om-text)]">{selected.provider}</span>
          {selected.model ? <span className="font-mono"> · {selected.model}</span> : null}
        </div>
      ) : null}
    </Modal>
  );
}
