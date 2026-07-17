import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Check,
  Clipboard,
  Loader2,
  Play,
  Plug,
  Radar,
  TerminalSquare,
  X,
} from "lucide-react";
import { demoApi } from "@/api";
import ProviderManagerModal from "@/components/providers/ProviderManagerModal";
import RotatingOrb from "@/components/shared/RotatingOrb";

const SDK_COMMANDS = [
  { label: "Run the basic Python SDK agent", command: "python examples/python_basic_agent.py" },
  { label: "Run the async Python SDK agent", command: "python examples/python_async_agent.py" },
];

const COLLECTOR_TARGETS = [
  { name: "Claude Code", hint: "openmesh run -- claude" },
  { name: "OpenAI agents", hint: "OpenMesh SDK: from openmesh import OpenMeshClient" },
  { name: "LangChain", hint: "python examples/langgraph_basic.py" },
  { name: "CrewAI", hint: "OpenMesh CrewAI integration (see docs/)" },
  { name: "MCP agents", hint: "openmesh mcp discover" },
  { name: "Custom SDK agents", hint: "client.emit(event) — OpenMesh event spec 0.1" },
];

/**
 * First-launch onboarding, rendered inside the existing graph empty state.
 * Four paths: run the temporary demo environment, connect a provider,
 * observe an already-running agent, or run the SDK examples.
 */
export default function FirstLaunchPanel() {
  const qc = useQueryClient();
  const [providerOpen, setProviderOpen] = useState(false);
  const [connectOpen, setConnectOpen] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  const startDemo = useMutation({
    mutationFn: demoApi.start,
    onSettled: () => qc.invalidateQueries(),
  });

  const copy = async (command: string) => {
    try {
      await navigator.clipboard.writeText(command);
      setCopied(command);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      setCopied(null);
    }
  };

  return (
    <div className="mt-5 text-left">
      <div className="grid gap-3 md:grid-cols-2">
        <OptionCard
          icon={<Play size={16} />}
          title="Run Demo Environment"
          description="Explore OpenMesh with simulated agents — Pioneer, Explorer, and Scientist — in a temporary demo workspace you can terminate at any time."
        >
          <button
            type="button"
            className="om-button mt-3 h-9 px-4 text-sm"
            disabled={startDemo.isPending}
            onClick={() => startDemo.mutate()}
          >
            {startDemo.isPending ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            Run Demo Environment
          </button>
        </OptionCard>

        <OptionCard
          icon={<Plug size={16} />}
          title="Connect AI Provider"
          description="Connect your own models — OpenAI, Anthropic, OpenRouter, or local runtimes. Keys are validated live and models are discovered from the provider."
        >
          <button type="button" className="om-button mt-3 h-9 px-4 text-sm" onClick={() => setProviderOpen(true)}>
            <Plug size={14} /> Connect AI Provider
          </button>
        </OptionCard>

        <OptionCard
          icon={<Radar size={16} />}
          title="Connect Existing Agent"
          description="Observe agents already running in Claude Code, OpenAI agents, LangChain, CrewAI, MCP agents, or your custom SDK agents."
        >
          <button type="button" className="om-button-ghost mt-3 h-9 px-4 text-sm" onClick={() => setConnectOpen(true)}>
            <Radar size={14} /> Connect Existing Agent
          </button>
        </OptionCard>

        <OptionCard
          icon={<TerminalSquare size={16} />}
          title="Run SDK Example"
          description="Instrument a real process with the OpenMesh Python SDK and watch it appear in the graph."
        >
          <div className="mt-3 space-y-2">
            {SDK_COMMANDS.map((item) => (
              <div key={item.command} className="flex items-center gap-2 rounded-[4px] border border-[color:var(--om-border)] bg-black/45 px-2 py-1.5">
                <code className="min-w-0 flex-1 truncate font-mono text-xs text-[color:var(--om-rust-300)]">{item.command}</code>
                <button
                  type="button"
                  className="om-button-ghost h-7 px-2 text-[11px]"
                  onClick={() => void copy(item.command)}
                >
                  {copied === item.command ? <Check size={12} /> : <Clipboard size={12} />}
                </button>
              </div>
            ))}
          </div>
        </OptionCard>
      </div>

      {providerOpen ? <ProviderManagerModal onClose={() => setProviderOpen(false)} /> : null}
      {connectOpen ? <ConnectAgentModal onClose={() => setConnectOpen(false)} onCopy={copy} copied={copied} /> : null}
    </div>
  );
}

function OptionCard({
  icon,
  title,
  description,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-[6px] border border-[color:var(--om-border)] bg-black/45 p-4">
      <div className="flex items-center gap-2 text-[color:var(--om-rust-300)]">
        {icon}
        <span className="text-sm font-bold uppercase tracking-[.1em]">{title}</span>
      </div>
      <p className="mt-2 text-sm leading-5 text-[color:var(--om-muted)]">{description}</p>
      {children}
    </div>
  );
}

function ConnectAgentModal({
  onClose,
  onCopy,
  copied,
}: {
  onClose: () => void;
  onCopy: (command: string) => Promise<void>;
  copied: string | null;
}) {
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 p-6 backdrop-blur-sm">
      <div className="om-card max-h-[90vh] w-full max-w-xl overflow-y-auto p-7">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4">
            <RotatingOrb size={48} />
            <div>
              <div className="om-kicker">OpenMesh Collector</div>
              <h1 className="text-xl font-black text-[color:var(--om-text)]">Connect Existing Agent</h1>
            </div>
          </div>
          <button type="button" className="om-button-ghost h-9 w-9 p-0" aria-label="Close" onClick={onClose}>
            <X size={16} />
          </button>
        </div>
        <p className="mt-3 text-sm text-[color:var(--om-muted)]">
          OpenMesh observes agents you already run — lifecycle, tool calls, file changes, commands, model and
          token usage — via the collector and SDK integrations. Point any of these at your running backend:
        </p>
        <div className="mt-4 space-y-2">
          {COLLECTOR_TARGETS.map((target) => (
            <div key={target.name} className="flex items-center gap-3 rounded-[4px] border border-[color:var(--om-border)] bg-black/45 px-3 py-2">
              <span className="w-36 shrink-0 text-sm font-semibold text-[color:var(--om-text)]">{target.name}</span>
              <code className="min-w-0 flex-1 truncate font-mono text-xs text-[color:var(--om-rust-300)]">{target.hint}</code>
              <button type="button" className="om-button-ghost h-7 px-2 text-[11px]" onClick={() => void onCopy(target.hint)}>
                {copied === target.hint ? <Check size={12} /> : <Clipboard size={12} />}
              </button>
            </div>
          ))}
        </div>
        <p className="mt-4 text-xs text-[color:var(--om-dim)]">
          Events use the OpenMesh spec (workspace, agent, event, trace) and can be posted to
          <code className="font-mono"> POST /api/openmesh/events</code>.
        </p>
      </div>
    </div>
  );
}
