import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import {
  Activity,
  AlertTriangle,
  BarChart2,
  GitBranch,
  Layers,
  Network,
  Radio,
  Server,
  ShieldCheck,
  Zap,
} from "lucide-react";
import { agentsApi, openmeshApi, statsApi } from "@/api";
import { brandText, cn } from "@/lib/utils";
import { useWSStore } from "@/store/wsStore";

type GraphNode = { id: string; name?: string; type?: string; event_count?: number; last_seen?: string };
type GraphEdge = { id: string; source: string; target: string; type?: string; event_count?: number; last_seen?: string };
type TraceSummary = { trace_id: string; status?: string; event_count?: number; started_at?: string };
type LocalLlmMetrics = {
  active_model_count?: number;
  average_latency_ms?: number | null;
  average_tokens_per_second?: number | null;
  provider_uptime?: { connected?: number; total?: number; ratio?: number };
};
type RuntimeMetrics = {
  active_runtimes?: number;
  detected_runtimes?: number;
  total_runtimes?: number;
  commands_executed?: number;
  files_modified?: number;
  model_requests?: number;
  runtime_uptime?: { available?: number; total?: number; ratio?: number };
};
type McpMetrics = {
  active_mcp_servers?: number;
  tool_calls?: number;
  failed_tool_calls?: number;
  resource_activity?: number;
  most_used_tools?: Array<{ tool?: string; calls?: number }>;
};
type WorkflowMetrics = {
  active_workflows?: number;
  completed_workflows?: number;
  average_handoffs?: number;
  busiest_agent?: { agent?: string; events?: number } | null;
  handoff_latency_ms?: number | null;
};
type ReplayMetrics = {
  metrics?: {
    events_replayed?: number;
    duration?: number | null;
    graph_mutations?: number;
    workflow_duration?: number | null;
  };
};
type DistributedNodeRegistry = {
  nodes?: Array<{
    node_id?: string;
    node_name?: string;
    node_type?: string;
    status?: string;
    last_seen?: string;
    uptime_seconds?: number;
    event_count?: number;
    hosted_counts?: {
      agents?: number;
      runtimes?: number;
      mcp_servers?: number;
    };
  }>;
  summary?: {
    node_count?: number;
    active_nodes?: number;
    hosted_agents?: number;
    hosted_runtimes?: number;
    hosted_mcp_servers?: number;
    host_relationships?: number;
  };
};
type FailureReport = {
  summary?: {
    failure_count?: number;
    active_failures?: number;
    resolved_failures?: number;
    failure_rate?: number;
    mttr_seconds?: number | null;
  };
  most_common_failures?: Array<{ name?: string; count?: number }>;
  failing_agents?: Array<{ name?: string; count?: number }>;
  failing_tools?: Array<{ name?: string; count?: number }>;
};
type ReputationAgent = {
  agent_id?: string;
  agent_name?: string;
  agent_score?: number;
  status?: string;
  metrics?: {
    success_rate?: number;
    workflow_completion_rate?: number;
    tool_reliability?: number;
    handoff_quality?: number;
    average_latency_ms?: number | null;
    reviews_completed?: number;
  };
};
type ReputationReport = {
  summary?: {
    agent_count?: number;
    average_agent_score?: number;
    trust_relationship_count?: number;
  };
  top_agents?: ReputationAgent[];
  top_reviewers?: ReputationAgent[];
  most_reliable_agents?: ReputationAgent[];
  fastest_agents?: ReputationAgent[];
};

export default function ObservatoryPage() {
  const { data: stats } = useQuery({ queryKey: ["stats"], queryFn: statsApi.get, refetchInterval: 30000 });
  const { data: agents = [] } = useQuery({ queryKey: ["agents"], queryFn: () => agentsApi.list(), refetchInterval: 30000 });
  const { data: graph = { nodes: [], edges: [] } } = useQuery({
    queryKey: ["openmesh-graph"],
    queryFn: () => openmeshApi.graph(),
    refetchInterval: 15000,
  });
  const { data: traces = [] } = useQuery({
    queryKey: ["openmesh-traces"],
    queryFn: () => openmeshApi.traces(),
    refetchInterval: 15000,
  });
  const { data: localLlm = {} } = useQuery<LocalLlmMetrics>({
    queryKey: ["openmesh-local-llm-metrics"],
    queryFn: () => openmeshApi.localLlmMetrics(),
    refetchInterval: 15000,
  });
  const { data: runtimeMetrics = {} } = useQuery<RuntimeMetrics>({
    queryKey: ["openmesh-runtime-metrics"],
    queryFn: () => openmeshApi.runtimeMetrics(),
    refetchInterval: 15000,
  });
  const { data: distributedNodes = {} } = useQuery<DistributedNodeRegistry>({
    queryKey: ["openmesh-distributed-nodes"],
    queryFn: () => openmeshApi.nodes(),
    refetchInterval: 15000,
  });
  const { data: failureReport = {} } = useQuery<FailureReport>({
    queryKey: ["openmesh-failure-report"],
    queryFn: () => openmeshApi.failureReport(),
    refetchInterval: 15000,
  });
  const { data: reputationReport = {} } = useQuery<ReputationReport>({
    queryKey: ["openmesh-reputation"],
    queryFn: () => openmeshApi.reputation(),
    refetchInterval: 15000,
  });
  const { data: mcpMetrics = {} } = useQuery<McpMetrics>({
    queryKey: ["openmesh-mcp-metrics"],
    queryFn: () => openmeshApi.mcpMetrics(),
    refetchInterval: 15000,
  });
  const { data: workflowMetrics = {} } = useQuery<WorkflowMetrics>({
    queryKey: ["openmesh-workflow-metrics"],
    queryFn: () => openmeshApi.workflowMetrics(),
    refetchInterval: 15000,
  });
  const { data: replayMetrics = {} } = useQuery<ReplayMetrics>({
    queryKey: ["openmesh-replay-metrics"],
    queryFn: () => openmeshApi.replayEcosystem({ limit: 500 }),
    refetchInterval: 15000,
  });
  const { events } = useWSStore();

  const graphNodes = graph.nodes as GraphNode[];
  const graphEdges = graph.edges as GraphEdge[];
  const traceList = traces as TraceSummary[];
  const nodeNames = new Map(graphNodes.map((node) => [node.id, node.name || node.id]));
  const activeAgentNodes = graphNodes.filter((node) => node.type === "agent");
  const processNodes = graphNodes.filter((node) => node.type === "process");
  const workflowNodes = graphNodes.filter((node) => node.type === "workflow");
  const serviceNodes = graphNodes.filter((node) =>
    ["service", "mcp_server", "capability", "framework", "database", "github_repository", "api_endpoint", "memory_store"].includes(node.type || ""),
  );
  const activeTraces = traceList.filter((trace) => trace.status === "active");
  const healthState = graphNodes.length > 0 || events.length > 0 ? "operational" : "waiting";
  const relationshipActivity = graphEdges.reduce((count, edge) => count + Number(edge.event_count || 0), 0);
  const topMcpTool = mcpMetrics.most_used_tools?.[0];
  const busiestAgent = workflowMetrics.busiest_agent;
  const replay = replayMetrics.metrics || {};
  const nodeSummary = distributedNodes.summary || {};
  const observedNodes = distributedNodes.nodes || [];
  const longestUptime = observedNodes.reduce((max, node) => Math.max(max, node.uptime_seconds || 0), 0);
  const failureSummary = failureReport.summary || {};
  const topFailure = failureReport.most_common_failures?.[0];
  const topFailingAgent = failureReport.failing_agents?.[0];
  const topFailingTool = failureReport.failing_tools?.[0];
  const reputationSummary = reputationReport.summary || {};
  const topAgent = reputationReport.top_agents?.[0];
  const topReviewer = reputationReport.top_reviewers?.[0];
  const mostReliableAgent = reputationReport.most_reliable_agents?.[0];
  const fastestAgent = reputationReport.fastest_agents?.[0];

  return (
    <div className="om-page">
      <div className="space-y-6">
        <header className="om-panel overflow-hidden p-0">
          <div className="om-rust-texture flex flex-col gap-6 border-b border-[color:var(--om-border)] p-6 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="om-kicker">OpenMesh Control Room</div>
              <h1 className="mt-2 flex items-center gap-2 text-3xl font-black text-[color:var(--om-text)]">
                <BarChart2 size={25} className="text-[color:var(--om-rust-300)]" /> Network Operations Center
              </h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-[color:var(--om-steel-300)]">
                Monitor agent activity, traces, workflows, relationships, and services as one living ecosystem.
              </p>
            </div>
            <div className="flex justify-start lg:justify-end">
              <img src="/brand/openmesh-logo.png" alt="OpenMesh" className="h-16 max-w-sm object-contain object-right mix-blend-screen opacity-95 drop-shadow-[0_0_18px_rgba(190,92,36,.24)]" />
            </div>
          </div>
        </header>

        <section className="grid gap-5 xl:grid-cols-[1.2fr_.8fr]">
          <ControlPanel title="Network Health" icon={<ShieldCheck size={16} />} className="min-h-64">
            <div className="grid gap-5 lg:grid-cols-[.8fr_1.2fr]">
              <div className="rounded-[6px] border border-[color:var(--om-border)] bg-black/35 p-5">
                <StatusPill status={healthState === "operational" ? "active" : "idle"} label={healthState === "operational" ? "Operational" : "Awaiting Activity"} />
                <div className="mt-5 font-mono text-5xl font-black text-[color:var(--om-text)]">{graphNodes.length}</div>
                <div className="stat-label mt-1">Observed Nodes</div>
                <p className="mt-4 text-sm leading-6 text-[color:var(--om-muted)]">
                  {healthState === "operational"
                    ? "The ecosystem graph has active structure and relationship evidence."
                    : "Run an example or observe a process to populate this station."}
                </p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <MetricCell label="Edges" value={graphEdges.length} />
                <MetricCell label="Events" value={events.length || stats?.messages || 0} />
                <MetricCell label="Traces" value={traceList.length} />
                <MetricCell label="Workflows" value={workflowNodes.length} />
                <MetricCell label="Processes" value={processNodes.length} />
                <MetricCell label="Rel Activity" value={relationshipActivity} />
                <MetricCell label="Local Models" value={localLlm.active_model_count || 0} />
                <MetricCell label="LLM Latency" value={formatMetric(localLlm.average_latency_ms, "ms")} />
                <MetricCell label="Tok/Sec" value={formatMetric(localLlm.average_tokens_per_second)} />
                <MetricCell
                  label="Provider Up"
                  value={`${localLlm.provider_uptime?.connected || 0}/${localLlm.provider_uptime?.total || 0}`}
                />
                <MetricCell label="Runtimes" value={`${runtimeMetrics.detected_runtimes || 0}/${runtimeMetrics.total_runtimes || 0}`} />
                <MetricCell label="Active Run" value={runtimeMetrics.active_runtimes || 0} />
                <MetricCell label="Commands" value={runtimeMetrics.commands_executed || 0} />
                <MetricCell label="Files Mod" value={runtimeMetrics.files_modified || 0} />
                <MetricCell label="Model Req" value={runtimeMetrics.model_requests || 0} />
                <MetricCell
                  label="Run Uptime"
                  value={`${runtimeMetrics.runtime_uptime?.available || 0}/${runtimeMetrics.runtime_uptime?.total || 0}`}
                />
                <MetricCell label="Active Nodes" value={nodeSummary.active_nodes || 0} />
                <MetricCell label="Node Uptime" value={formatDuration(longestUptime)} />
                <MetricCell label="Hosted Agents" value={nodeSummary.hosted_agents || 0} />
                <MetricCell label="Hosted Runtime" value={nodeSummary.hosted_runtimes || 0} />
                <MetricCell label="Hosted MCP" value={nodeSummary.hosted_mcp_servers || 0} />
                <MetricCell label="Host Edges" value={nodeSummary.host_relationships || 0} />
                <MetricCell label="Failures" value={failureSummary.failure_count || 0} />
                <MetricCell label="Fail Rate" value={`${failureSummary.failure_rate || 0}%`} />
                <MetricCell label="MTTR" value={formatDuration(failureSummary.mttr_seconds)} />
                <MetricCell label="Active Fail" value={failureSummary.active_failures || 0} />
                <MetricCell label="Agents Scored" value={reputationSummary.agent_count || 0} />
                <MetricCell label="Avg Score" value={formatMetric(reputationSummary.average_agent_score)} />
                <MetricCell label="Trust Edges" value={reputationSummary.trust_relationship_count || 0} />
                <MetricCell label="Top Score" value={formatMetric(topAgent?.agent_score)} />
                <MetricCell label="MCP Active" value={mcpMetrics.active_mcp_servers || 0} />
                <MetricCell label="Tool Calls" value={mcpMetrics.tool_calls || 0} />
                <MetricCell label="Tool Failed" value={mcpMetrics.failed_tool_calls || 0} />
                <MetricCell label="Resources" value={mcpMetrics.resource_activity || 0} />
                <MetricCell label="Top Tool" value={topMcpTool?.tool ? `${topMcpTool.tool} (${topMcpTool.calls || 0})` : "-"} />
                <MetricCell label="Active WF" value={workflowMetrics.active_workflows || 0} />
                <MetricCell label="Done WF" value={workflowMetrics.completed_workflows || 0} />
                <MetricCell label="Avg Handoff" value={formatMetric(workflowMetrics.average_handoffs)} />
                <MetricCell label="Handoff Lat" value={formatMetric(workflowMetrics.handoff_latency_ms, "ms")} />
                <MetricCell label="Busy Agent" value={busiestAgent?.agent ? `${busiestAgent.agent} (${busiestAgent.events || 0})` : "-"} />
                <MetricCell label="Replay Ev" value={replay.events_replayed || 0} />
                <MetricCell label="Replay Mut" value={replay.graph_mutations || 0} />
                <MetricCell label="Replay Dur" value={formatMetric(replay.duration, "s")} />
                <MetricCell label="WF Replay" value={formatMetric(replay.workflow_duration, "s")} />
              </div>
            </div>
          </ControlPanel>

          <ControlPanel title="Recent Events" icon={<Radio size={16} />} className="min-h-64">
            {events.length === 0 ? (
              <EmptyOperationalMessage text="No live websocket events are present in this browser session." />
            ) : (
              <div className="space-y-2">
                {events.slice(0, 8).map((event) => (
                  <div key={event.id} className="flex items-start gap-3 border-b border-[color:var(--om-border)]/50 pb-2 last:border-0">
                    <span className="om-status-dot om-status-active mt-1.5 shrink-0" />
                    <div className="min-w-0">
                      <div className="truncate text-sm text-[color:var(--om-text)]">{event.type}</div>
                      <div className="truncate text-xs text-[color:var(--om-muted)]">
                        {brandText(event.data?.source?.name, "OpenMesh")} {event.data?.target?.name ? `-> ${brandText(event.data.target.name)}` : ""}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </ControlPanel>
        </section>

        <section className="grid gap-5 xl:grid-cols-3">
          <ControlPanel title="Active Agents" icon={<Zap size={16} />}>
            <EntityList
              empty="No agent nodes observed yet."
              items={(activeAgentNodes.length ? activeAgentNodes : (agents as GraphNode[])).slice(0, 7).map((node) => ({
                id: node.id,
                title: brandText(node.name, "Unknown agent"),
                subtitle: node.type || "agent",
                value: `${node.event_count || 0} ev`,
                status: "active",
              }))}
            />
          </ControlPanel>

          <ControlPanel title="Active Traces" icon={<Activity size={16} />}>
            <EntityList
              empty="No traces are currently active."
              items={(activeTraces.length ? activeTraces : traceList).slice(0, 7).map((trace) => ({
                id: trace.trace_id,
                title: trace.trace_id,
                subtitle: trace.status || "unknown",
                value: `${trace.event_count || 0} ev`,
                status: trace.status === "active" ? "active" : "idle",
              }))}
            />
          </ControlPanel>

          <ControlPanel title="Relationships" icon={<GitBranch size={16} />}>
            <EntityList
              empty="No graph relationships have been reduced yet."
              items={graphEdges.slice(0, 7).map((edge) => ({
                id: edge.id,
                title: `${nodeNames.get(edge.source) || edge.source} -> ${nodeNames.get(edge.target) || edge.target}`,
                subtitle: edge.type || "relationship",
                value: `${edge.event_count || 0} obs`,
                status: "active",
              }))}
            />
          </ControlPanel>
        </section>

        <section className="grid gap-5 xl:grid-cols-3">
          <ControlPanel title="Agent Reputation" icon={<ShieldCheck size={16} />}>
            <div className="grid grid-cols-2 gap-3">
              <MetricCell label="Scored" value={reputationSummary.agent_count || 0} />
              <MetricCell label="Trust Edges" value={reputationSummary.trust_relationship_count || 0} />
            </div>
            <div className="mt-4 space-y-3">
              <ReputationInsight label="Top Agent" agent={topAgent} metric="agent_score" />
              <ReputationInsight label="Top Reviewer" agent={topReviewer} metric="reviews_completed" />
              <ReputationInsight label="Most Reliable" agent={mostReliableAgent} metric="tool_reliability" />
              <ReputationInsight label="Fastest" agent={fastestAgent} metric="average_latency_ms" suffix="ms" />
            </div>
          </ControlPanel>

          <ControlPanel title="Failure Intelligence" icon={<AlertTriangle size={16} />}>
            <div className="grid grid-cols-2 gap-3">
              <MetricCell label="Active" value={failureSummary.active_failures || 0} />
              <MetricCell label="Resolved" value={failureSummary.resolved_failures || 0} />
            </div>
            <div className="mt-4 space-y-3">
              <FailureInsight label="Common" value={topFailure ? `${topFailure.name} (${topFailure.count || 0})` : "none"} />
              <FailureInsight label="Agent" value={topFailingAgent ? `${topFailingAgent.name} (${topFailingAgent.count || 0})` : "none"} />
              <FailureInsight label="Tool" value={topFailingTool ? `${topFailingTool.name} (${topFailingTool.count || 0})` : "none"} />
            </div>
          </ControlPanel>

          <ControlPanel title="Distributed Nodes" icon={<Server size={16} />}>
            <EntityList
              empty="No OpenMesh nodes have joined this ecosystem yet."
              items={observedNodes.slice(0, 7).map((node) => {
                const hosted = node.hosted_counts || {};
                return {
                  id: node.node_id || node.node_name || "node",
                  title: brandText(node.node_name, node.node_id || "OpenMesh node"),
                  subtitle: `${node.node_type || "node"} host`,
                  value: `${hosted.agents || 0} ag / ${hosted.runtimes || 0} rt / ${hosted.mcp_servers || 0} mcp`,
                  status: node.status === "active" ? "active" : "idle",
                };
              })}
            />
          </ControlPanel>

          <ControlPanel title="Workflows" icon={<Layers size={16} />}>
            <EntityList
              empty="No workflow nodes are visible yet."
              items={workflowNodes.slice(0, 7).map((node) => ({
                id: node.id,
                title: brandText(node.name, node.id),
                subtitle: "workflow",
                value: `${node.event_count || 0} ev`,
                status: "idle",
              }))}
            />
          </ControlPanel>

          <ControlPanel title="Services" icon={<Server size={16} />}>
            <EntityList
              empty="No services, MCP servers, or capabilities observed yet."
              items={serviceNodes.slice(0, 7).map((node) => ({
                id: node.id,
                title: brandText(node.name, node.id),
                subtitle: node.type || "service",
                value: `${node.event_count || 0} ev`,
                status: "idle",
              }))}
            />
          </ControlPanel>

          <ControlPanel title="Ecosystem Summary" icon={<Network size={16} />}>
            <div className="grid grid-cols-2 gap-3">
              <MetricCell label="Agents" value={activeAgentNodes.length || stats?.agents || 0} />
              <MetricCell label="Guilds" value={stats?.guilds || 0} />
              <MetricCell label="Wiki" value={stats?.wiki_pages || 0} />
              <MetricCell label="Posts" value={stats?.posts || 0} />
            </div>
            <div className="mt-4 rounded-[4px] border border-[color:var(--om-border)] bg-black/30 p-3 text-xs leading-5 text-[color:var(--om-muted)]">
              Daily operation starts in Graph, then fans out through traces, workflows, and relationship evidence.
            </div>
          </ControlPanel>
        </section>
      </div>
    </div>
  );
}

function ControlPanel({ title, icon, className, children }: { title: string; icon: ReactNode; className?: string; children: ReactNode }) {
  return (
    <section className={cn("card p-5", className)}>
      <div className="mb-5 flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-sm font-bold text-[color:var(--om-text)]">
          <span className="text-[color:var(--om-rust-400)]">{icon}</span>
          {title}
        </h2>
        <span className="h-px flex-1 bg-[color:var(--om-border)]" />
      </div>
      {children}
    </section>
  );
}

function MetricCell({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="om-stat">
      <div className="om-stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

function formatMetric(value?: number | null, suffix = "") {
  if (value === null || value === undefined) return "-";
  const formatted = Number.isInteger(value) ? String(value) : value.toFixed(1);
  return suffix ? `${formatted}${suffix}` : formatted;
}

function formatDuration(seconds?: number | null) {
  if (!seconds) return "-";
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  return `${Math.floor(minutes / 60)}h`;
}

function StatusPill({ status, label }: { status: "active" | "idle" | "failed"; label: string }) {
  return (
    <span className="om-badge">
      <span className={cn("om-status-dot", status === "active" && "om-status-active", status === "idle" && "om-status-idle", status === "failed" && "om-status-failed")} />
      {label}
    </span>
  );
}

function EntityList({
  items,
  empty,
}: {
  items: Array<{ id: string; title: string; subtitle: string; value: string; status: "active" | "idle" | "failed" }>;
  empty: string;
}) {
  if (items.length === 0) return <EmptyOperationalMessage text={empty} />;
  return (
    <div className="space-y-3">
      {items.map((item) => (
        <div key={item.id} className="flex items-center gap-3 rounded-[4px] border border-[color:var(--om-border)] bg-black/25 px-4 py-3">
          <span className={cn("om-status-dot shrink-0", item.status === "active" && "om-status-active", item.status === "idle" && "om-status-idle", item.status === "failed" && "om-status-failed")} />
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-semibold text-[color:var(--om-text)]">{item.title}</div>
            <div className="truncate text-xs text-[color:var(--om-muted)]">{item.subtitle}</div>
          </div>
          <div className="font-mono text-xs text-[color:var(--om-rust-300)]">{item.value}</div>
        </div>
      ))}
    </div>
  );
}

function EmptyOperationalMessage({ text }: { text: string }) {
  return (
    <div className="rounded-[4px] border border-dashed border-[color:var(--om-border)] bg-black/25 p-5 text-sm leading-6 text-[color:var(--om-dim)]">
      {text}
    </div>
  );
}

function FailureInsight({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-[4px] border border-[color:var(--om-border)] bg-black/25 px-4 py-3">
      <span className="stat-label">{label}</span>
      <span className="truncate text-right font-mono text-xs text-[color:var(--om-rust-300)]">{value}</span>
    </div>
  );
}

function ReputationInsight({
  label,
  agent,
  metric,
  suffix = "",
}: {
  label: string;
  agent?: ReputationAgent;
  metric: "agent_score" | "reviews_completed" | "tool_reliability" | "average_latency_ms";
  suffix?: string;
}) {
  const value =
    metric === "agent_score"
      ? agent?.agent_score
      : metric === "reviews_completed"
        ? agent?.metrics?.reviews_completed
        : metric === "tool_reliability"
          ? agent?.metrics?.tool_reliability
          : agent?.metrics?.average_latency_ms;
  return (
    <div className="flex items-center justify-between gap-3 rounded-[4px] border border-[color:var(--om-border)] bg-black/25 px-4 py-3">
      <span className="stat-label">{label}</span>
      <span className="truncate text-right font-mono text-xs text-[color:var(--om-rust-300)]">
        {agent?.agent_name ? `${agent.agent_name} (${formatMetric(value, suffix)})` : "none"}
      </span>
    </div>
  );
}
