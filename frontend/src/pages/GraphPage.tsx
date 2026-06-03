import {
  useMemo,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
  type ReactNode,
  type WheelEvent as ReactWheelEvent,
} from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Crosshair,
  Filter,
  GitBranch,
  Info,
  Network,
  Search,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { openmeshApi } from "@/api";
import { cn } from "@/lib/utils";
import type {
  OpenMeshGraph,
  OpenMeshGraphEdge,
  OpenMeshGraphNode,
  OpenMeshNodeInspection,
  OpenMeshTimeline,
  OpenMeshTraceDetail,
  OpenMeshTraceSummary,
} from "@/types/openmesh";

const NODE_LIMIT = 220;
const EDGE_LIMIT = 480;
const CANVAS_WIDTH = 1200;
const CANVAS_HEIGHT = 720;

type Viewport = { x: number; y: number; zoom: number };
type DragState = { x: number; y: number; panX: number; panY: number };
type LayoutNode = OpenMeshGraphNode & {
  x: number;
  y: number;
  radius: number;
  degree: number;
};

const NODE_STYLES: Record<string, { fill: string; stroke: string; text: string }> = {
  agent: { fill: "#c56b2c", stroke: "#f1b37f", text: "#fde6cf" },
  tool: { fill: "#64748b", stroke: "#cbd5e1", text: "#e2e8f0" },
  workflow: { fill: "#8a4f2a", stroke: "#d28a50", text: "#f8d3b0" },
  process: { fill: "#3f454b", stroke: "#94a3b8", text: "#dbe4ee" },
  service: { fill: "#334155", stroke: "#9ca3af", text: "#d1d5db" },
  mcp_server: { fill: "#6f5134", stroke: "#d6a45f", text: "#f3dcc1" },
  capability: { fill: "#46565f", stroke: "#a8b5bd", text: "#e4edf2" },
  framework: { fill: "#5f4230", stroke: "#c8834a", text: "#f2c9a8" },
};

const DEFAULT_NODE_STYLE = { fill: "#2f3437", stroke: "#858b91", text: "#d5d7da" };

export default function GraphPage() {
  const [search, setSearch] = useState("");
  const [nodeType, setNodeType] = useState("all");
  const [relationshipType, setRelationshipType] = useState("all");
  const [lifecycle, setLifecycle] = useState("all");
  const [depth, setDepth] = useState(2);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [viewport, setViewport] = useState<Viewport>({ x: 0, y: 0, zoom: 1 });
  const dragRef = useRef<DragState | null>(null);

  const { data: graph = { nodes: [], edges: [] } } = useQuery({
    queryKey: ["openmesh-graph-view"],
    queryFn: () => openmeshApi.graph({ limit: 5000 }),
    refetchInterval: 15000,
  });
  const { data: traces = [] } = useQuery({
    queryKey: ["openmesh-graph-traces"],
    queryFn: () => openmeshApi.traces(80),
    refetchInterval: 15000,
  });
  const { data: ecosystem } = useQuery({
    queryKey: ["openmesh-graph-ecosystem"],
    queryFn: openmeshApi.ecosystem,
    refetchInterval: 30000,
  });
  const { data: selectedInspection } = useQuery({
    queryKey: ["openmesh-node-inspection", selectedNodeId],
    queryFn: () => openmeshApi.inspectNode(selectedNodeId || ""),
    enabled: Boolean(selectedNodeId),
  });
  const { data: selectedTrace } = useQuery({
    queryKey: ["openmesh-trace-detail", selectedTraceId],
    queryFn: () => openmeshApi.trace(selectedTraceId || ""),
    enabled: Boolean(selectedTraceId),
  });
  const { data: selectedTraceTimeline } = useQuery({
    queryKey: ["openmesh-trace-timeline", selectedTraceId],
    queryFn: () => openmeshApi.traceTimeline(selectedTraceId || ""),
    enabled: Boolean(selectedTraceId),
  });
  const { data: timeline } = useQuery({
    queryKey: ["openmesh-graph-timeline"],
    queryFn: () => openmeshApi.timeline(2500),
    refetchInterval: 30000,
  });

  const nodesById = useMemo(() => new Map(graph.nodes.map((node) => [node.id, node])), [graph.nodes]);
  const selectedNode = selectedNodeId ? nodesById.get(selectedNodeId) || null : null;
  const selectedEdge = useMemo(
    () => graph.edges.find((edge) => edge.id === selectedEdgeId) || null,
    [graph.edges, selectedEdgeId],
  );

  const nodeTypeOptions = useMemo(() => uniqueSorted(graph.nodes.map((node) => node.type)), [graph.nodes]);
  const relationshipOptions = useMemo(() => uniqueSorted(graph.edges.map((edge) => edge.type)), [graph.edges]);
  const lifecycleOptions = useMemo(
    () => uniqueSorted(graph.edges.map((edge) => edge.lifecycle_state || "unknown")),
    [graph.edges],
  );

  const visibleGraph = useMemo(
    () =>
      buildVisibleGraph(graph, {
        search,
        nodeType,
        relationshipType,
        lifecycle,
        selectedNodeId,
        depth,
      }),
    [depth, graph, lifecycle, nodeType, relationshipType, search, selectedNodeId],
  );

  const layout = useMemo(
    () => buildLayout(visibleGraph.nodes, visibleGraph.edges, selectedNodeId),
    [selectedNodeId, visibleGraph.edges, visibleGraph.nodes],
  );
  const traceHighlights = useMemo(
    () => buildTraceHighlights(graph, selectedTraceId, selectedTrace),
    [graph, selectedTrace, selectedTraceId],
  );
  const graphStats = useMemo(() => graphStatistics(graph), [graph]);
  const visibleStats = useMemo(() => graphStatistics(visibleGraph), [visibleGraph]);

  const handleWheel = (event: ReactWheelEvent<SVGSVGElement>) => {
    event.preventDefault();
    const direction = event.deltaY > 0 ? -0.08 : 0.08;
    setViewport((current) => ({ ...current, zoom: clamp(current.zoom + direction, 0.45, 2.4) }));
  };

  const handleMouseDown = (event: ReactMouseEvent<SVGSVGElement>) => {
    if (event.button !== 0) return;
    dragRef.current = { x: event.clientX, y: event.clientY, panX: viewport.x, panY: viewport.y };
  };

  const handleMouseMove = (event: ReactMouseEvent<SVGSVGElement>) => {
    if (!dragRef.current) return;
    const drag = dragRef.current;
    setViewport((current) => ({
      ...current,
      x: drag.panX + event.clientX - drag.x,
      y: drag.panY + event.clientY - drag.y,
    }));
  };

  const stopDrag = () => {
    dragRef.current = null;
  };

  const clearSelection = () => {
    setSelectedNodeId(null);
    setSelectedEdgeId(null);
  };

  return (
    <div className="om-page text-stone-200">
      <div className="space-y-4">
        <header className="om-panel flex flex-col gap-4 p-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="flex items-center gap-3 text-[color:var(--om-rust-400)]">
              <img src="/brand/openmesh-wheel.png" alt="" className="h-10 w-10 rounded-[6px] border border-[color:var(--om-border-strong)] object-cover" />
              <Network size={22} />
              <span className="om-kicker">OpenMesh Graph Explorer</span>
            </div>
            <h1 className="om-title mt-2 text-3xl">Agent Network Map</h1>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-[color:var(--om-muted)]">
              Explore observed agents, tools, workflows, MCP servers, capabilities, traces, relationships, and provenance.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
            <Metric label="Nodes" value={graphStats.nodeCount} />
            <Metric label="Edges" value={graphStats.edgeCount} />
            <Metric label="Visible" value={visibleStats.nodeCount} />
            <Metric label="Traces" value={traces.length} />
          </div>
        </header>

        <section className="grid gap-4 xl:grid-cols-[280px_minmax(0,1fr)_360px]">
          <GraphControls
            search={search}
            setSearch={setSearch}
            nodeType={nodeType}
            setNodeType={setNodeType}
            relationshipType={relationshipType}
            setRelationshipType={setRelationshipType}
            lifecycle={lifecycle}
            setLifecycle={setLifecycle}
            depth={depth}
            setDepth={setDepth}
            nodeTypeOptions={nodeTypeOptions}
            relationshipOptions={relationshipOptions}
            lifecycleOptions={lifecycleOptions}
            onReset={() => {
              setSearch("");
              setNodeType("all");
              setRelationshipType("all");
              setLifecycle("all");
              setDepth(2);
              clearSelection();
              setSelectedTraceId(null);
            }}
          />

          <div className="om-panel min-w-0 overflow-hidden rounded-[8px]">
            <div className="om-panel-header flex items-center justify-between px-3 py-2">
              <div className="flex items-center gap-2 text-sm font-medium text-stone-100">
                <GitBranch size={15} className="text-[color:var(--om-rust-400)]" />
                Network Map
              </div>
              <div className="flex items-center gap-1">
                <IconButton label="Zoom out" onClick={() => setViewport((v) => ({ ...v, zoom: clamp(v.zoom - 0.12, 0.45, 2.4) }))}>
                  <ZoomOut size={14} />
                </IconButton>
                <IconButton label="Zoom in" onClick={() => setViewport((v) => ({ ...v, zoom: clamp(v.zoom + 0.12, 0.45, 2.4) }))}>
                  <ZoomIn size={14} />
                </IconButton>
                <IconButton label="Reset view" onClick={() => setViewport({ x: 0, y: 0, zoom: 1 })}>
                  <Crosshair size={14} />
                </IconButton>
              </div>
            </div>

            <div className="relative h-[680px] bg-[color:var(--om-iron-980)]">
              {graph.nodes.length === 0 ? <EmptyGraphOnboarding /> : null}
              {graph.nodes.length > 0 && visibleGraph.nodes.length === 0 ? (
                <div className="absolute inset-0 z-10 flex items-center justify-center bg-black/80">
                  <div className="om-empty max-w-md p-5 text-sm text-[color:var(--om-muted)]">
                    No entities match the current graph filters.
                  </div>
                </div>
              ) : null}
              <svg
                className="h-full w-full cursor-grab select-none"
                role="img"
                viewBox={`0 0 ${CANVAS_WIDTH} ${CANVAS_HEIGHT}`}
                onWheel={handleWheel}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={stopDrag}
                onMouseLeave={stopDrag}
                onClick={(event) => {
                  if (event.currentTarget === event.target) {
                    setSelectedEdgeId(null);
                  }
                }}
              >
                <defs>
                  <marker id="graph-arrow" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto" markerUnits="strokeWidth">
                    <path d="M0,0 L9,4.5 L0,9 Z" fill="#6f6256" />
                  </marker>
                  <marker id="graph-arrow-hot" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto" markerUnits="strokeWidth">
                    <path d="M0,0 L9,4.5 L0,9 Z" fill="#c56b2c" />
                  </marker>
                </defs>
                <rect width={CANVAS_WIDTH} height={CANVAS_HEIGHT} fill="#050504" />
                <GridLines />
                <g transform={`translate(${viewport.x} ${viewport.y}) scale(${viewport.zoom})`}>
                  {visibleGraph.edges.map((edge) => {
                    const source = layout.get(edge.source);
                    const target = layout.get(edge.target);
                    if (!source || !target) return null;
                    const highlighted = edge.id === selectedEdgeId || traceHighlights.edgeIds.has(edge.id);
                    const selected = edge.id === selectedEdgeId;
                    return (
                      <g
                        key={edge.id}
                        className="cursor-pointer"
                        onMouseDown={(event) => event.stopPropagation()}
                        onClick={(event) => {
                          event.stopPropagation();
                          setSelectedEdgeId(edge.id);
                        }}
                      >
                        <line
                          x1={source.x}
                          y1={source.y}
                          x2={target.x}
                          y2={target.y}
                          stroke={highlighted ? "#c56b2c" : "#49443d"}
                          strokeWidth={selected ? 4 : highlighted ? 3 : 1.4}
                          markerEnd={highlighted ? "url(#graph-arrow-hot)" : "url(#graph-arrow)"}
                          opacity={selected || highlighted ? 0.95 : 0.62}
                        />
                        {(selected || highlighted) && (
                          <text
                            x={(source.x + target.x) / 2}
                            y={(source.y + target.y) / 2 - 8}
                            textAnchor="middle"
                            className="pointer-events-none fill-[#f1d0ad] text-[11px] font-medium"
                          >
                            {edge.type}
                          </text>
                        )}
                      </g>
                    );
                  })}
                  {visibleGraph.nodes.map((node) => {
                    const layoutNode = layout.get(node.id);
                    if (!layoutNode) return null;
                    const style = NODE_STYLES[node.type] || DEFAULT_NODE_STYLE;
                    const selected = node.id === selectedNodeId;
                    const highlighted = selected || traceHighlights.nodeIds.has(node.id);
                    return (
                      <g
                        key={node.id}
                        className="cursor-pointer"
                        transform={`translate(${layoutNode.x} ${layoutNode.y})`}
                        onMouseDown={(event) => event.stopPropagation()}
                        onClick={(event) => {
                          event.stopPropagation();
                          setSelectedNodeId(node.id);
                          setSelectedEdgeId(null);
                        }}
                      >
                        <circle
                          r={layoutNode.radius + (selected ? 8 : highlighted ? 5 : 0)}
                          fill="transparent"
                          stroke={highlighted ? "#c56b2c" : "#2f2a24"}
                          strokeWidth={selected ? 3 : 1.5}
                          opacity={highlighted ? 0.95 : 0.65}
                        />
                        <circle
                          r={layoutNode.radius}
                          fill={style.fill}
                          stroke={style.stroke}
                          strokeWidth={selected ? 2.5 : 1.5}
                        />
                        <text y={layoutNode.radius + 17} textAnchor="middle" className="pointer-events-none fill-stone-300 text-[11px]">
                          {shortText(node.name, 20)}
                        </text>
                        <text y={4} textAnchor="middle" className="pointer-events-none text-[10px] font-semibold" fill={style.text}>
                          {node.type.slice(0, 3).toUpperCase()}
                        </text>
                      </g>
                    );
                  })}
                </g>
              </svg>
              <div className="absolute bottom-3 left-3 rounded-[4px] border border-[color:var(--om-border)] bg-[rgba(18,16,13,.95)] px-3 py-2 font-mono text-xs text-[color:var(--om-muted)]">
                rendered {visibleGraph.nodes.length}/{graph.nodes.length} nodes, {visibleGraph.edges.length}/{graph.edges.length} relationships
              </div>
            </div>
          </div>

          <InspectorPanel
            selectedNode={selectedNode}
            selectedEdge={selectedEdge}
            inspection={selectedInspection}
            nodesById={nodesById}
            selectedTraceId={selectedTraceId}
            onTraceSelect={setSelectedTraceId}
          />
        </section>

        <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
          <TraceStrip
            traces={traces}
            selectedTraceId={selectedTraceId}
            onSelect={setSelectedTraceId}
            selectedTrace={selectedTrace}
            selectedTraceTimeline={selectedTraceTimeline}
          />
          <EvolutionPanel timeline={selectedTraceTimeline || timeline} ecosystem={ecosystem} />
        </section>
      </div>
    </div>
  );
}

function GraphControls({
  search,
  setSearch,
  nodeType,
  setNodeType,
  relationshipType,
  setRelationshipType,
  lifecycle,
  setLifecycle,
  depth,
  setDepth,
  nodeTypeOptions,
  relationshipOptions,
  lifecycleOptions,
  onReset,
}: {
  search: string;
  setSearch: (value: string) => void;
  nodeType: string;
  setNodeType: (value: string) => void;
  relationshipType: string;
  setRelationshipType: (value: string) => void;
  lifecycle: string;
  setLifecycle: (value: string) => void;
  depth: number;
  setDepth: (value: number) => void;
  nodeTypeOptions: string[];
  relationshipOptions: string[];
  lifecycleOptions: string[];
  onReset: () => void;
}) {
  return (
    <aside className="om-panel space-y-3 p-4">
      <div className="flex items-center gap-2 text-sm font-semibold text-stone-100">
        <Filter size={15} className="text-[#c56b2c]" />
        Graph Controls
      </div>
      <label className="block">
        <span className="mb-1 flex items-center gap-1 text-xs text-[color:var(--om-muted)]">
          <Search size={12} /> Search
        </span>
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="agent, tool, trace, event"
          className="om-input"
        />
      </label>
      <SelectControl label="Entity type" value={nodeType} onChange={setNodeType} options={nodeTypeOptions} />
      <SelectControl label="Relationship" value={relationshipType} onChange={setRelationshipType} options={relationshipOptions} />
      <SelectControl label="Lifecycle" value={lifecycle} onChange={setLifecycle} options={lifecycleOptions} />
      <div>
        <div className="mb-2 flex items-center justify-between text-xs text-[color:var(--om-muted)]">
          <span>Depth</span>
          <span className="font-mono text-[color:var(--om-rust-400)]">{depth}</span>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" className="om-button-ghost h-9 w-9 p-0" onClick={() => setDepth(clamp(depth - 1, 1, 4))}>
            -
          </button>
          <input
            type="range"
            min={1}
            max={4}
            value={depth}
            onChange={(event) => setDepth(Number(event.target.value))}
            className="w-full accent-[color:var(--om-rust-500)]"
          />
          <button type="button" className="om-button-ghost h-9 w-9 p-0" onClick={() => setDepth(clamp(depth + 1, 1, 4))}>
            +
          </button>
        </div>
      </div>
      <button type="button" className="om-button w-full" onClick={onReset}>
        Reset graph view
      </button>
      <div className="border-t border-[color:var(--om-border)] pt-3 text-xs leading-5 text-[color:var(--om-muted)]">
        <p>Select a node to focus its neighborhood.</p>
        <p>Select a trace below to highlight participating entities.</p>
      </div>
    </aside>
  );
}

function SelectControl({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-[color:var(--om-muted)]">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="om-select"
      >
        <option value="all">All</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function InspectorPanel({
  selectedNode,
  selectedEdge,
  inspection,
  nodesById,
  selectedTraceId,
  onTraceSelect,
}: {
  selectedNode: OpenMeshGraphNode | null;
  selectedEdge: OpenMeshGraphEdge | null;
  inspection?: OpenMeshNodeInspection;
  nodesById: Map<string, OpenMeshGraphNode>;
  selectedTraceId: string | null;
  onTraceSelect: (traceId: string) => void;
}) {
  if (selectedEdge) {
    const source = nodesById.get(selectedEdge.source);
    const target = nodesById.get(selectedEdge.target);
    const provenance = selectedEdge.provenance || {};
    return (
      <aside className="om-panel p-4">
        <PanelTitle icon={<GitBranch size={15} />} title="Relationship Inspector" />
        <div className="mt-4 space-y-4">
          <div>
            <div className="text-sm font-semibold text-stone-100">{selectedEdge.type}</div>
            <div className="mt-1 text-xs text-stone-500">
              {source?.name || selectedEdge.source} -&gt; {target?.name || selectedEdge.target}
            </div>
          </div>
          <KeyValueGrid
            rows={[
              ["state", selectedEdge.lifecycle_state || "unknown"],
              ["validation", selectedEdge.validation_status || "unknown"],
              ["observations", String(selectedEdge.observation_count || selectedEdge.event_count || 0)],
              ["first seen", formatTime(selectedEdge.first_seen || provenance.first_seen)],
              ["last seen", formatTime(selectedEdge.last_seen || provenance.last_seen)],
            ]}
          />
          <TokenList label="Traces" values={provenance.trace_ids || []} active={selectedTraceId} onSelect={onTraceSelect} />
          <TokenList label="Events" values={provenance.event_ids || []} />
        </div>
      </aside>
    );
  }

  if (!selectedNode) {
    return (
      <aside className="om-panel p-4">
        <PanelTitle icon={<Info size={15} />} title="Inspector" />
        <div className="mt-4 text-sm leading-6 text-stone-500">
          Select a node or relationship in the graph to inspect provenance, traces, metadata, and relationships.
        </div>
      </aside>
    );
  }

  const node = inspection?.node || selectedNode;
  const metadata = node.metadata || {};
  const incoming = inspection?.incoming_relationships || [];
  const outgoing = inspection?.outgoing_relationships || [];
  const traceIds = inspection?.trace_ids || node.provenance?.trace_ids || [];

  return (
    <aside className="om-panel max-h-[780px] overflow-auto p-4">
      <PanelTitle icon={<Info size={15} />} title="Node Inspector" />
      <div className="mt-4">
        <div className="text-lg font-semibold text-stone-50">{node.name}</div>
        <div className="text-xs text-[#c56b2c]">{node.type}</div>
      </div>
      <KeyValueGrid
        rows={[
          ["status", node.lifecycle_state || "observed"],
          ["validation", node.validation_status || "unknown"],
          ["first seen", formatTime(inspection?.first_seen || node.first_seen)],
          ["last seen", formatTime(inspection?.last_seen || node.last_seen)],
          ["events", String(inspection?.event_count || node.event_count || 0)],
          ["relationships", String(inspection?.relationship_count || node.relationship_count || incoming.length + outgoing.length)],
        ]}
      />
      <TokenList label="Traces" values={traceIds} active={selectedTraceId} onSelect={onTraceSelect} />
      <TokenList label="Sessions" values={inspection?.session_ids || node.provenance?.session_ids || []} />
      <RelationshipList title="Incoming" edges={incoming} nodesById={nodesById} direction="incoming" />
      <RelationshipList title="Outgoing" edges={outgoing} nodesById={nodesById} direction="outgoing" />
      <div className="mt-4">
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-stone-500">Metadata</div>
        {Object.keys(metadata).length === 0 ? (
          <div className="text-xs text-stone-600">No metadata recorded.</div>
        ) : (
          <div className="space-y-2">
            {Object.entries(metadata).slice(0, 12).map(([key, value]) => (
              <div key={key} className="border border-[#2f2a24] bg-[#090806] px-3 py-2 text-xs">
                <div className="text-stone-500">{key}</div>
                <div className="mt-1 break-words text-stone-300">{String(value)}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}

function RelationshipList({
  title,
  edges,
  nodesById,
  direction,
}: {
  title: string;
  edges: OpenMeshGraphEdge[];
  nodesById: Map<string, OpenMeshGraphNode>;
  direction: "incoming" | "outgoing";
}) {
  return (
    <div className="mt-4">
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-stone-500">{title}</div>
      {edges.length === 0 ? (
        <div className="text-xs text-stone-600">None</div>
      ) : (
        <div className="space-y-2">
          {edges.slice(0, 8).map((edge) => {
            const peer = direction === "incoming" ? nodesById.get(edge.source) : nodesById.get(edge.target);
            return (
              <div key={edge.id} className="border border-[#2f2a24] bg-[#090806] px-3 py-2 text-xs">
                <div className="text-stone-300">{edge.type}</div>
                <div className="text-stone-500">{peer?.name || (direction === "incoming" ? edge.source : edge.target)}</div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function TraceStrip({
  traces,
  selectedTraceId,
  onSelect,
  selectedTrace,
  selectedTraceTimeline,
}: {
  traces: OpenMeshTraceSummary[];
  selectedTraceId: string | null;
  onSelect: (traceId: string | null) => void;
  selectedTrace?: OpenMeshTraceDetail;
  selectedTraceTimeline?: OpenMeshTimeline;
}) {
  return (
    <section className="om-panel p-4">
      <div className="flex items-center justify-between gap-3">
        <PanelTitle icon={<Activity size={15} />} title="Trace Integration" />
        {selectedTraceId ? (
          <button type="button" className="text-xs text-stone-500 hover:text-[#f1d0ad]" onClick={() => onSelect(null)}>
            Clear trace
          </button>
        ) : null}
      </div>
      <div className="mt-3 grid gap-3 lg:grid-cols-[320px_minmax(0,1fr)]">
        <div className="max-h-56 overflow-auto rounded-[4px] border border-[color:var(--om-border)]">
          {traces.length === 0 ? (
            <div className="p-3 text-sm text-stone-500">No traces observed yet.</div>
          ) : (
            traces.slice(0, 24).map((trace) => (
              <button
                key={trace.trace_id}
                type="button"
                onClick={() => onSelect(trace.trace_id)}
                className={cn(
                  "block w-full border-b border-[#2f2a24] px-3 py-2 text-left text-xs last:border-0",
                  selectedTraceId === trace.trace_id ? "bg-[#3a2418] text-[#f1d0ad]" : "text-stone-400 hover:bg-[#11100e]",
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate font-medium">{trace.trace_id}</span>
                  <span>{trace.event_count}</span>
                </div>
                <div className="mt-1 text-stone-600">
                  {trace.status} / {formatTime(trace.started_at)}
                </div>
              </button>
            ))
          )}
        </div>
        <div className="min-h-40 rounded-[4px] border border-[color:var(--om-border)] bg-black/35 p-3">
          {!selectedTraceId ? (
            <div className="text-sm text-stone-500">Select a trace to highlight graph entities and relationships.</div>
          ) : (
            <div className="space-y-3">
              <div>
                <div className="text-sm font-semibold text-stone-100">{selectedTraceId}</div>
                <div className="text-xs text-stone-500">
                  {selectedTrace?.status || "loading"} / {selectedTrace?.event_count || 0} events
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2 text-xs">
                <Metric label="Agents" value={selectedTrace?.agents?.length || 0} />
                <Metric label="Tools" value={selectedTrace?.tools?.length || 0} />
                <Metric label="Frames" value={selectedTraceTimeline?.timeline?.length || 0} />
              </div>
              <div>
                <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-stone-500">Graph Evolution</div>
                <TimelineRows timeline={selectedTraceTimeline} />
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function EvolutionPanel({ timeline, ecosystem }: { timeline?: OpenMeshTimeline; ecosystem?: unknown }) {
  const summary = timeline?.summary || {};
  const ecosystemSummary = getRecord(getRecord(ecosystem, "summary"));
  return (
    <section className="om-panel p-4">
      <PanelTitle icon={<Activity size={15} />} title="Evolution" />
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <Metric label="Events" value={Number(summary.events || 0)} />
        <Metric label="Changes" value={Number(summary.relationship_changes || 0)} />
        <Metric label="Entities" value={Number(ecosystemSummary.entity_count || 0)} />
        <Metric label="Relations" value={Number(ecosystemSummary.relationship_count || 0)} />
      </div>
      <div className="mt-3">
        <TimelineRows timeline={timeline} />
      </div>
    </section>
  );
}

function TimelineRows({ timeline }: { timeline?: OpenMeshTimeline }) {
  const rows = [...(timeline?.relationship_changes || []), ...(timeline?.timeline || [])]
    .sort((a, b) => String(b.timestamp || "").localeCompare(String(a.timestamp || "")))
    .slice(0, 8);
  if (rows.length === 0) {
    return <div className="text-xs text-stone-600">No evolution records loaded.</div>;
  }
  return (
    <div className="space-y-2">
      {rows.map((row, index) => (
        <div key={`${String(row.timestamp || "row")}-${index}`} className="border border-[#2f2a24] bg-[#090806] px-3 py-2 text-xs">
          <div className="text-stone-300">{timelineLabel(row)}</div>
          <div className="mt-1 text-stone-600">{formatTime(String(row.timestamp || ""))}</div>
        </div>
      ))}
    </div>
  );
}

function EmptyGraphOnboarding() {
  return (
    <div className="absolute inset-0 z-10 flex items-center justify-center bg-[color:var(--om-iron-980)]/95 p-6">
      <div className="om-empty w-full max-w-3xl">
        <img src="/brand/openmesh-logo.png" alt="OpenMesh" className="mx-auto h-14 max-w-md object-contain" />
        <div className="om-kicker mt-6">No graph data yet</div>
        <h2 className="mt-2 text-2xl font-bold text-stone-50">Start observing an agent or process</h2>
        <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-[color:var(--om-muted)]">
          OpenMesh becomes useful when events create relationships. Run one command and the graph will populate with nodes, traces, and provenance.
        </p>
        <div className="mt-5 grid gap-3 text-left font-mono text-xs text-[color:var(--om-steel-300)] md:grid-cols-2">
          <code className="rounded-[4px] border border-[color:var(--om-border)] bg-black/45 p-3">openmesh run -- python -c "print('hello openmesh')"</code>
          <code className="rounded-[4px] border border-[color:var(--om-border)] bg-black/45 p-3">python examples/python_basic_agent.py</code>
          <code className="rounded-[4px] border border-[color:var(--om-border)] bg-black/45 p-3">python examples/python_async_agent.py</code>
          <code className="rounded-[4px] border border-[color:var(--om-border)] bg-black/45 p-3">python examples/langgraph_basic.py</code>
        </div>
        <div className="mt-4 text-sm text-[color:var(--om-muted)]">
          Example entities will appear as agents, tools, workflows, processes, services, MCP servers, and capabilities.
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="om-stat px-3 py-2">
      <div className="om-stat-value text-base">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

function PanelTitle({ icon, title }: { icon: ReactNode; title: string }) {
  return (
    <div className="flex items-center gap-2 text-sm font-semibold text-stone-100">
      <span className="text-[color:var(--om-rust-400)]">{icon}</span>
      {title}
    </div>
  );
}

function IconButton({ label, children, onClick }: { label: string; children: ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      onClick={onClick}
      className="flex h-8 w-8 items-center justify-center rounded-[4px] border border-[color:var(--om-border)] bg-black/45 text-[color:var(--om-steel-400)] transition hover:border-[color:var(--om-border-strong)] hover:text-[color:var(--om-rust-300)]"
    >
      {children}
    </button>
  );
}

function KeyValueGrid({ rows }: { rows: Array<[string, string]> }) {
  return (
    <div className="mt-4 grid grid-cols-2 gap-2">
      {rows.map(([label, value]) => (
        <div key={label} className="rounded-[4px] border border-[color:var(--om-border)] bg-black/35 px-3 py-2">
          <div className="stat-label">{label}</div>
          <div className="mt-1 truncate text-xs text-[color:var(--om-steel-300)]">{value}</div>
        </div>
      ))}
    </div>
  );
}

function TokenList({
  label,
  values,
  active,
  onSelect,
}: {
  label: string;
  values: string[];
  active?: string | null;
  onSelect?: (value: string) => void;
}) {
  return (
    <div className="mt-4">
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-stone-500">{label}</div>
      {values.length === 0 ? (
        <div className="text-xs text-stone-600">None</div>
      ) : (
        <div className="flex flex-wrap gap-2">
          {values.slice(0, 12).map((value) => (
            <button
              key={value}
              type="button"
              disabled={!onSelect}
              onClick={() => onSelect?.(value)}
              className={cn(
                "max-w-full truncate border px-2 py-1 text-xs",
                active === value
                  ? "border-[#c56b2c] bg-[#3a2418] text-[#f1d0ad]"
                  : "border-[#2f2a24] bg-[#090806] text-stone-500",
                onSelect ? "hover:border-[#c56b2c] hover:text-[#f1d0ad]" : "cursor-default",
              )}
            >
              {shortText(value, 28)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function GridLines() {
  const lines = [];
  for (let x = 0; x <= CANVAS_WIDTH; x += 80) {
    lines.push(<line key={`x-${x}`} x1={x} y1={0} x2={x} y2={CANVAS_HEIGHT} stroke="#16130f" strokeWidth={1} />);
  }
  for (let y = 0; y <= CANVAS_HEIGHT; y += 80) {
    lines.push(<line key={`y-${y}`} x1={0} y1={y} x2={CANVAS_WIDTH} y2={y} stroke="#16130f" strokeWidth={1} />);
  }
  return <g>{lines}</g>;
}

function buildVisibleGraph(
  graph: OpenMeshGraph,
  filters: {
    search: string;
    nodeType: string;
    relationshipType: string;
    lifecycle: string;
    selectedNodeId: string | null;
    depth: number;
  },
): OpenMeshGraph {
  const nodesById = new Map(graph.nodes.map((node) => [node.id, node]));
  const search = normalize(filters.search);
  let edges = graph.edges.filter((edge) => {
    if (filters.relationshipType !== "all" && edge.type !== filters.relationshipType) return false;
    if (filters.lifecycle !== "all" && (edge.lifecycle_state || "unknown") !== filters.lifecycle) return false;
    return true;
  });
  let nodeIds = new Set(
    graph.nodes.filter((node) => filters.nodeType === "all" || node.type === filters.nodeType).map((node) => node.id),
  );

  if (search) {
    const searchNodeIds = new Set(graph.nodes.filter((node) => nodeMatches(node, search)).map((node) => node.id));
    const searchEdgeIds = new Set(
      edges.filter((edge) => edgeMatches(edge, nodesById, search) || searchNodeIds.has(edge.source) || searchNodeIds.has(edge.target)).map((edge) => edge.id),
    );
    nodeIds = new Set(searchNodeIds);
    edges = edges.filter((edge) => {
      if (!searchEdgeIds.has(edge.id)) return false;
      nodeIds.add(edge.source);
      nodeIds.add(edge.target);
      return true;
    });
  } else {
    edges = edges.filter((edge) => {
      if (nodeIds.has(edge.source) || nodeIds.has(edge.target)) {
        nodeIds.add(edge.source);
        nodeIds.add(edge.target);
        return true;
      }
      return false;
    });
  }

  if (filters.selectedNodeId && nodesById.has(filters.selectedNodeId)) {
    const neighborhood = expandNeighborhood(filters.selectedNodeId, edges, filters.depth);
    nodeIds = neighborhood.nodeIds;
    edges = edges.filter((edge) => neighborhood.edgeIds.has(edge.id));
  }

  const degree = degreeMap(edges);
  const sortedNodes = Array.from(nodeIds)
    .map((id) => nodesById.get(id))
    .filter((node): node is OpenMeshGraphNode => Boolean(node))
    .sort((a, b) => {
      if (a.id === filters.selectedNodeId) return -1;
      if (b.id === filters.selectedNodeId) return 1;
      return (degree.get(b.id) || 0) - (degree.get(a.id) || 0) || a.name.localeCompare(b.name);
    })
    .slice(0, NODE_LIMIT);
  const renderedIds = new Set(sortedNodes.map((node) => node.id));
  const renderedEdges = edges.filter((edge) => renderedIds.has(edge.source) && renderedIds.has(edge.target)).slice(0, EDGE_LIMIT);
  return { nodes: sortedNodes, edges: renderedEdges, validation: graph.validation };
}

function expandNeighborhood(rootId: string, edges: OpenMeshGraphEdge[], depth: number) {
  const nodeIds = new Set<string>([rootId]);
  const edgeIds = new Set<string>();
  let frontier = new Set<string>([rootId]);
  for (let level = 0; level < depth; level += 1) {
    const next = new Set<string>();
    for (const edge of edges) {
      if (frontier.has(edge.source) || frontier.has(edge.target)) {
        edgeIds.add(edge.id);
        if (!nodeIds.has(edge.source)) next.add(edge.source);
        if (!nodeIds.has(edge.target)) next.add(edge.target);
        nodeIds.add(edge.source);
        nodeIds.add(edge.target);
      }
    }
    frontier = next;
    if (frontier.size === 0) break;
  }
  return { nodeIds, edgeIds };
}

function buildLayout(nodes: OpenMeshGraphNode[], edges: OpenMeshGraphEdge[], selectedNodeId: string | null): Map<string, LayoutNode> {
  const degree = degreeMap(edges);
  const positions = new Map<string, LayoutNode>();
  const centerX = CANVAS_WIDTH / 2;
  const centerY = CANVAS_HEIGHT / 2;
  const selected = selectedNodeId ? nodes.find((node) => node.id === selectedNodeId) : undefined;
  const ordered = [...nodes].sort((a, b) => (degree.get(b.id) || 0) - (degree.get(a.id) || 0) || a.name.localeCompare(b.name));

  if (selected) {
    positions.set(selected.id, withPosition(selected, centerX, centerY, degree.get(selected.id) || 0));
    const neighborIds = new Set(edges.filter((edge) => edge.source === selected.id || edge.target === selected.id).flatMap((edge) => [edge.source, edge.target]));
    neighborIds.delete(selected.id);
    const neighbors = ordered.filter((node) => neighborIds.has(node.id));
    const remainder = ordered.filter((node) => node.id !== selected.id && !neighborIds.has(node.id));
    placeRing(neighbors, positions, centerX, centerY, 190, degree, -Math.PI / 2);
    placeRing(remainder, positions, centerX, centerY, 330, degree, -Math.PI / 3);
  } else {
    const grouped = groupByType(ordered);
    const typeNames = Object.keys(grouped).sort();
    let placed = 0;
    for (const type of typeNames) {
      const items = grouped[type];
      for (const item of items) {
        const angle = (placed / Math.max(ordered.length, 1)) * Math.PI * 2 - Math.PI / 2;
        const ring = 170 + (typeNames.indexOf(type) % 3) * 95 + (placed % 2) * 35;
        positions.set(item.id, withPosition(item, centerX + Math.cos(angle) * ring, centerY + Math.sin(angle) * ring, degree.get(item.id) || 0));
        placed += 1;
      }
    }
  }

  return positions;
}

function placeRing(
  nodes: OpenMeshGraphNode[],
  positions: Map<string, LayoutNode>,
  centerX: number,
  centerY: number,
  radius: number,
  degree: Map<string, number>,
  offset: number,
) {
  nodes.forEach((node, index) => {
    const angle = offset + (index / Math.max(nodes.length, 1)) * Math.PI * 2;
    positions.set(node.id, withPosition(node, centerX + Math.cos(angle) * radius, centerY + Math.sin(angle) * radius, degree.get(node.id) || 0));
  });
}

function withPosition(node: OpenMeshGraphNode, x: number, y: number, degree: number): LayoutNode {
  return { ...node, x, y, degree, radius: clamp(15 + Math.sqrt((node.event_count || 1) + degree) * 2.5, 18, 34) };
}

function buildTraceHighlights(graph: OpenMeshGraph, traceId: string | null, trace?: OpenMeshTraceDetail) {
  const nodeIds = new Set<string>();
  const edgeIds = new Set<string>();
  if (!traceId) return { nodeIds, edgeIds };
  for (const event of trace?.events || []) {
    if (event.source?.node_id) nodeIds.add(event.source.node_id);
    if (event.target?.node_id) nodeIds.add(event.target.node_id);
  }
  for (const edge of graph.edges) {
    if (edge.provenance?.trace_ids?.includes(traceId)) {
      edgeIds.add(edge.id);
      nodeIds.add(edge.source);
      nodeIds.add(edge.target);
    }
  }
  return { nodeIds, edgeIds };
}

function graphStatistics(graph: OpenMeshGraph) {
  return {
    nodeCount: graph.nodes.length,
    edgeCount: graph.edges.length,
  };
}

function degreeMap(edges: OpenMeshGraphEdge[]) {
  const degree = new Map<string, number>();
  for (const edge of edges) {
    degree.set(edge.source, (degree.get(edge.source) || 0) + 1);
    degree.set(edge.target, (degree.get(edge.target) || 0) + 1);
  }
  return degree;
}

function groupByType(nodes: OpenMeshGraphNode[]) {
  return nodes.reduce<Record<string, OpenMeshGraphNode[]>>((groups, node) => {
    groups[node.type] = [...(groups[node.type] || []), node];
    return groups;
  }, {});
}

function uniqueSorted(values: string[]) {
  return Array.from(new Set(values.filter(Boolean))).sort();
}

function nodeMatches(node: OpenMeshGraphNode, search: string) {
  return normalize([node.id, node.name, node.type, node.runtime, JSON.stringify(node.metadata || {})].join(" ")).includes(search);
}

function edgeMatches(edge: OpenMeshGraphEdge, nodesById: Map<string, OpenMeshGraphNode>, search: string) {
  const source = nodesById.get(edge.source);
  const target = nodesById.get(edge.target);
  return normalize(
    [
      edge.id,
      edge.type,
      source?.name,
      target?.name,
      edge.provenance?.trace_ids?.join(" "),
      edge.provenance?.event_ids?.join(" "),
    ].join(" "),
  ).includes(search);
}

function timelineLabel(row: Record<string, unknown>) {
  const kind = String(row.kind || row.event_type || row.action || "change");
  const source = row.source_name || row.source;
  const target = row.target_name || row.target;
  if (source && target) return `${kind}: ${String(source)} ${String(row.relationship_type || "")} ${String(target)}`;
  if (row.description) return String(row.description);
  if (row.name) return `${kind}: ${String(row.name)}`;
  return kind;
}

function getRecord(value: unknown, key?: string): Record<string, unknown> {
  const source = key && isRecord(value) ? value[key] : value;
  return isRecord(source) ? source : {};
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function normalize(value: string) {
  return value.trim().toLowerCase();
}

function shortText(value: string | undefined, length: number) {
  const text = value || "-";
  return text.length <= length ? text : `${text.slice(0, length - 1)}...`;
}

function formatTime(value?: string) {
  if (!value) return "-";
  return value.replace("T", " ").replace("Z", "").slice(0, 19);
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}
