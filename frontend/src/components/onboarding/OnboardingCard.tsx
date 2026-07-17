import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, KeyRound, Loader2, Play, XCircle } from "lucide-react";
import { controlApi, settingsApi } from "@/api";
import RotatingOrb from "@/components/shared/RotatingOrb";
import { cn } from "@/lib/utils";

const PROVIDERS = [
  { id: "anthropic", label: "Anthropic" },
  { id: "openai", label: "OpenAI" },
  { id: "openrouter", label: "OpenRouter" },
];

type TestState =
  | { kind: "idle" }
  | { kind: "testing" }
  | { kind: "ok"; message: string }
  | { kind: "fail"; message: string };

/**
 * First-run onboarding: shown when GET /api/settings/provider reports that no
 * LLM provider is configured. Lets the user pick a provider, paste a key,
 * test it, save it (hot-reloaded server side), and start the default agent —
 * all without touching a terminal or .env file.
 */
export default function OnboardingCard() {
  const qc = useQueryClient();
  const [provider, setProvider] = useState("anthropic");
  const [apiKey, setApiKey] = useState("");
  const [test, setTest] = useState<TestState>({ kind: "idle" });
  const [saved, setSaved] = useState(false);
  const [starting, setStarting] = useState(false);

  const testMutation = useMutation({
    mutationFn: () => settingsApi.testProvider({ provider, api_key: apiKey }),
    onMutate: () => setTest({ kind: "testing" }),
    onSuccess: (result) =>
      setTest(
        result.connected
          ? { kind: "ok", message: `${result.provider_name}: ${result.message}` }
          : { kind: "fail", message: `${result.provider_name}: ${result.message}` },
      ),
    onError: (error: any) =>
      setTest({ kind: "fail", message: error?.response?.data?.detail || "Connection test failed" }),
  });

  const saveMutation = useMutation({
    mutationFn: () => settingsApi.saveProvider({ provider, api_key: apiKey }),
    onSuccess: () => {
      setSaved(true);
      setTest({ kind: "idle" });
    },
    onError: (error: any) =>
      setTest({ kind: "fail", message: error?.response?.data?.detail || "Saving the key failed" }),
  });

  const startAgent = async () => {
    setStarting(true);
    try {
      await controlApi.startAgents();
    } finally {
      setStarting(false);
      // Refetch settings + live status so the card hides and the top bar flips.
      qc.invalidateQueries({ queryKey: ["provider-settings"] });
      qc.invalidateQueries({ queryKey: ["live-status"] });
    }
  };

  const busy = testMutation.isPending || saveMutation.isPending;

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 p-6 backdrop-blur-sm">
      <div className="om-card w-full max-w-lg p-8">
        <div className="flex items-center gap-5">
          <RotatingOrb size={72} />
          <div>
            <div className="om-kicker">First Launch</div>
            <h1 className="text-2xl font-black text-[color:var(--om-text)]">Connect a provider</h1>
            <p className="mt-1 text-sm text-[color:var(--om-muted)]">
              Paste an API key once — agents start from the browser, no terminal needed.
            </p>
          </div>
        </div>

        {!saved ? (
          <form
            className="mt-7 space-y-5"
            onSubmit={(event) => {
              event.preventDefault();
              if (apiKey.trim()) saveMutation.mutate();
            }}
          >
            <label className="block">
              <span className="om-kicker">Provider</span>
              <select
                className="om-select mt-2 w-full"
                value={provider}
                onChange={(event) => {
                  setProvider(event.target.value);
                  setTest({ kind: "idle" });
                }}
              >
                {PROVIDERS.map((p) => (
                  <option key={p.id} value={p.id}>{p.label}</option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="om-kicker">API key</span>
              <div className="relative mt-2">
                <KeyRound size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[color:var(--om-dim)]" />
                <input
                  type="password"
                  autoComplete="off"
                  spellCheck={false}
                  className="om-input w-full pl-9"
                  placeholder="sk-…"
                  value={apiKey}
                  onChange={(event) => {
                    setApiKey(event.target.value);
                    setTest({ kind: "idle" });
                  }}
                />
              </div>
              <span className="mt-2 block text-xs text-[color:var(--om-dim)]">
                Stored encrypted on this machine (~/.openmesh) — never sent anywhere except the provider.
              </span>
            </label>

            {test.kind === "ok" || test.kind === "fail" ? (
              <div
                className={cn(
                  "flex items-start gap-2 rounded-[4px] border px-3 py-2 text-sm",
                  test.kind === "ok"
                    ? "border-[color:var(--om-green-500)] text-[color:var(--om-green-500)]"
                    : "border-red-700 text-red-400",
                )}
              >
                {test.kind === "ok" ? <CheckCircle2 size={16} className="mt-0.5 shrink-0" /> : <XCircle size={16} className="mt-0.5 shrink-0" />}
                <span className="break-words">{test.message}</span>
              </div>
            ) : null}

            <div className="flex gap-3">
              <button
                type="button"
                className="om-button-ghost flex-1"
                disabled={!apiKey.trim() || busy}
                onClick={() => testMutation.mutate()}
              >
                {test.kind === "testing" ? <Loader2 size={15} className="animate-spin" /> : null}
                Test Connection
              </button>
              <button type="submit" className="om-button flex-1" disabled={!apiKey.trim() || busy}>
                {saveMutation.isPending ? <Loader2 size={15} className="animate-spin" /> : null}
                Save
              </button>
            </div>
          </form>
        ) : (
          <div className="mt-7 space-y-5 text-center">
            <div className="flex items-center justify-center gap-2 text-lg font-bold text-[color:var(--om-green-500)]">
              <CheckCircle2 size={20} />
              Connected
            </div>
            <p className="text-sm text-[color:var(--om-muted)]">
              Provider saved and hot-reloaded. Start the default agent and watch the graph come alive.
            </p>
            <button type="button" className="om-button mx-auto px-6" disabled={starting} onClick={startAgent}>
              {starting ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
              Start Agent
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
