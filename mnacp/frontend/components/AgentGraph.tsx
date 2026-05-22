"use client";

import { memo, useCallback, useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import ReactFlow, {
  Node,
  Edge,
  EdgeProps,
  Background,
  Controls,
  MiniMap,
  NodeProps,
  useNodesState,
  useEdgesState,
  MarkerType,
  getBezierPath,
  Handle,
  Position,
} from "reactflow";
import "reactflow/dist/style.css";
import { Agent, fetchAgents } from "@/lib/api";

// ─── Status colours ─────────────────────────────────────────────────────────────
const STATUS_COLOR: Record<string, string> = {
  online: "#22c55e",
  offline: "#ef4444",
  busy: "#f59e0b",
};

const STATUS_BG: Record<string, string> = {
  online: "bg-emerald-100 text-emerald-700",
  offline: "bg-red-100 text-red-700",
  busy: "bg-amber-100 text-amber-700",
};

// ─── Custom agent node ──────────────────────────────────────────────────────────
const AgentNode = memo(({ data }: NodeProps) => {
  const statusColor = STATUS_COLOR[data.status] ?? "#94a3b8";
  const statusBg = STATUS_BG[data.status] ?? "bg-gray-100 text-gray-600";
  const trust = Math.round((data.trust_score ?? 0) * 100);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.7 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.5 }}
      transition={{ type: "spring", stiffness: 260, damping: 20 }}
      className="rounded-xl bg-white border-2 shadow-md px-3 py-2.5 w-[148px]"
      style={{ borderColor: statusColor, boxShadow: `0 0 0 3px ${statusColor}22` }}
    >
      {/* Çoklu handle — kenarlar en uygun kenardan bağlanabilsin */}
      <Handle id="top"    type="target" position={Position.Top}    style={{ opacity: 0 }} />
      <Handle id="left"   type="target" position={Position.Left}   style={{ opacity: 0 }} />
      <Handle id="right"  type="source" position={Position.Right}  style={{ opacity: 0 }} />
      <Handle id="bottom" type="source" position={Position.Bottom} style={{ opacity: 0 }} />

      <div className="flex items-center gap-1.5 mb-1">
        <span className="h-2 w-2 rounded-full flex-shrink-0" style={{ backgroundColor: statusColor }} />
        <span className="font-semibold text-gray-800 text-xs truncate">{data.label}</span>
      </div>
      <div className="text-[10px] text-gray-400 mb-1.5">{data.toolCount} araç</div>
      <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${statusBg}`}>
        {data.status}
      </span>
      <div className="mt-2">
        <div className="flex justify-between text-[9px] text-gray-400 mb-0.5">
          <span>güven</span>
          <span>{trust}%</span>
        </div>
        <div className="h-1 rounded-full bg-gray-100 overflow-hidden">
          <motion.div
            className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500"
            initial={{ width: 0 }}
            animate={{ width: `${trust}%` }}
            transition={{ duration: 0.8, ease: "easeOut" }}
          />
        </div>
      </div>
    </motion.div>
  );
});
AgentNode.displayName = "AgentNode";

// ─── Custom orchestrator node ──────────────────────────────────────────────────
const OrchestratorNode = memo(() => (
  <motion.div
    initial={{ opacity: 0, scale: 0.6 }}
    animate={{ opacity: 1, scale: 1 }}
    exit={{ opacity: 0, scale: 0.4 }}
    transition={{ type: "spring", stiffness: 200, damping: 18 }}
    className="rounded-full flex flex-col items-center justify-center bg-gradient-to-br from-indigo-600 to-violet-600 text-white shadow-lg"
    style={{
      width: 120,
      height: 120,
      boxShadow: "0 0 0 4px rgba(99,102,241,0.25), 0 0 24px rgba(99,102,241,0.4)",
    }}
  >
    <Handle id="top"    type="target" position={Position.Top}    style={{ opacity: 0 }} />
    <Handle id="left"   type="target" position={Position.Left}   style={{ opacity: 0 }} />
    <Handle id="right"  type="source" position={Position.Right}  style={{ opacity: 0 }} />
    <Handle id="bottom" type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    <div className="text-xs font-bold text-center leading-tight">Orkestratör</div>
    <div className="text-[10px] text-indigo-200 mt-0.5">koordinatör</div>
  </motion.div>
));
OrchestratorNode.displayName = "OrchestratorNode";

// ─── Custom bezier edge — sıralı çizim animasyonu ──────────────────────────────
interface EdgeData {
  status?: "running" | "done" | "failed";
  label?: string;
  order?: number;
}

const SequencedEdge = memo(
  ({
    id,
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    data,
    style,
    markerEnd,
  }: EdgeProps<EdgeData>) => {
    const [edgePath, labelX, labelY] = getBezierPath({
      sourceX,
      sourceY,
      sourcePosition,
      targetX,
      targetY,
      targetPosition,
      curvature: 0.35,
    });

    const isRunning = data?.status === "running";
    const order = data?.order ?? 0;
    const delay = order * 0.45; // her edge bir öncekinden 0.45s sonra çizilir
    const stroke = (style?.stroke as string) ?? "#6366f1";

    return (
      <>
        {/* Arka plan path — orijinal path'i marker ile gösterir, animasyon overlay */}
        <motion.path
          id={id}
          d={edgePath}
          fill="none"
          stroke={stroke}
          strokeWidth={isRunning ? 3 : 2.4}
          strokeLinecap="round"
          opacity={0.95}
          markerEnd={markerEnd as string | undefined}
          initial={{ pathLength: 0, opacity: 0 }}
          animate={{ pathLength: 1, opacity: 0.95 }}
          transition={{ pathLength: { duration: 0.9, delay, ease: "easeInOut" }, opacity: { duration: 0.2, delay } }}
          style={
            isRunning
              ? {
                  strokeDasharray: "8 5",
                  animation: "flowEdge 0.6s linear infinite",
                  filter: `drop-shadow(0 0 6px ${stroke}88)`,
                }
              : undefined
          }
        />
        {data?.label && (
          <motion.g
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: delay + 0.5, duration: 0.3 }}
          >
            <rect
              x={labelX - 16}
              y={labelY - 9}
              width={32}
              height={18}
              rx={9}
              fill="white"
              stroke={stroke}
              strokeWidth={1}
              opacity={0.95}
            />
            <text
              x={labelX}
              y={labelY + 4}
              textAnchor="middle"
              style={{ fontSize: 10, fill: stroke, fontWeight: 600 }}
            >
              {data.label}
            </text>
          </motion.g>
        )}
      </>
    );
  },
);
SequencedEdge.displayName = "SequencedEdge";

// ─── Node / edge registries ─────────────────────────────────────────────────────
const NODE_TYPES = { agentNode: AgentNode, orchestratorNode: OrchestratorNode };
const EDGE_TYPES = { sequenced: SequencedEdge };

const ORCHESTRATOR_ID = "orchestrator";

// ─── Layout — halka düzeni ──────────────────────────────────────────────────────
function agentsToGraph(
  agents: Agent[],
  showOrchestrator: boolean,
): { nodes: Node[]; edges: Edge[] } {
  const ringRadiusX = 300;
  const ringRadiusY = 195;
  const cx = 340;
  const cy = 290;

  const nodes: Node[] = agents.map((agent, i) => ({
    id: agent.agent_id,
    type: "agentNode",
    position: {
      x: cx + Math.cos((i / agents.length) * 2 * Math.PI) * ringRadiusX - 74,
      y: cy + Math.sin((i / agents.length) * 2 * Math.PI) * ringRadiusY - 50,
    },
    data: {
      label: agent.name,
      status: agent.status,
      toolCount: agent.tools.length,
      trust_score: agent.trust_score,
    },
  }));

  if (showOrchestrator) {
    nodes.push({
      id: ORCHESTRATOR_ID,
      type: "orchestratorNode",
      position: { x: cx - 60, y: cy - 60 },
      data: {},
    });
  }
  return { nodes, edges: [] };
}

// ─── Edge colour map ────────────────────────────────────────────────────────────
const EDGE_COLOR: Record<string, string> = {
  running: "#f59e0b",
  done: "#22c55e",
  failed: "#ef4444",
};

interface Props {
  delegationEdges?: Array<{
    from: string;
    to: string;
    label?: string;
    status?: "running" | "done" | "failed";
  }>;
  showOrchestrator?: boolean;
}

export default function AgentGraph({
  delegationEdges = [],
  showOrchestrator = false,
}: Props) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  const loadAgents = useCallback(async () => {
    try {
      const data: Agent[] = await fetchAgents();
      const { nodes: n } = agentsToGraph(data, showOrchestrator);
      setNodes(n);
    } catch {
      // registry henüz ayakta değil
    }
  }, [setNodes, showOrchestrator]);

  useEffect(() => {
    loadAgents();
    const id = setInterval(loadAgents, 5000);
    return () => clearInterval(id);
  }, [loadAgents]);

  useEffect(() => {
    const dynamicEdges: Edge<EdgeData>[] = delegationEdges.map((e, i) => {
      const color = EDGE_COLOR[e.status ?? "running"] ?? "#6366f1";
      return {
        id: `e${i}-${e.from}-${e.to}`,
        source: e.from,
        target: e.to,
        type: "sequenced",
        markerEnd: { type: MarkerType.ArrowClosed, color, width: 18, height: 18 },
        style: { stroke: color },
        data: { status: e.status ?? "running", label: e.label, order: i },
      };
    });
    setEdges(dynamicEdges);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(delegationEdges)]);

  return (
    <div className="h-[500px] w-full rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      {nodes.length === 0 ? (
        <div className="flex h-full items-center justify-center text-gray-400 text-sm">
          Registry bağlantısı bekleniyor…
        </div>
      ) : (
        <AnimatePresence>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={NODE_TYPES}
            edgeTypes={EDGE_TYPES}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            proOptions={{ hideAttribution: true }}
            defaultEdgeOptions={{ type: "sequenced" }}
          >
            <Background color="#e2e8f0" gap={20} />
            <Controls />
            <MiniMap
              nodeColor={(n) => {
                if (n.id === ORCHESTRATOR_ID) return "#6366f1";
                return STATUS_COLOR[n.data?.status] ?? "#94a3b8";
              }}
              maskColor="rgba(248,250,252,0.7)"
              style={{ background: "#f1f5f9", border: "1px solid #e2e8f0" }}
            />
          </ReactFlow>
        </AnimatePresence>
      )}
    </div>
  );
}
