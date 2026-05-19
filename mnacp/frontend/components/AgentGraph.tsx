"use client";

import { useCallback, useEffect } from "react";
import ReactFlow, {
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
} from "reactflow";
import "reactflow/dist/style.css";
import { Agent, fetchAgents } from "@/lib/api";

const STATUS_COLOR: Record<string, string> = {
  online: "#22c55e",
  offline: "#ef4444",
  busy: "#f59e0b",
};

const ORCHESTRATOR_ID = "orchestrator";

function agentsToGraph(
  agents: Agent[],
  showOrchestrator: boolean,
): { nodes: Node[]; edges: Edge[] } {
  const ringRadiusX = 280;
  const ringRadiusY = 180;
  const cx = 320;
  const cy = 280;
  const nodes: Node[] = agents.map((agent, i) => ({
    id: agent.agent_id,
    position: {
      x: cx + Math.cos((i / agents.length) * 2 * Math.PI) * ringRadiusX,
      y: cy + Math.sin((i / agents.length) * 2 * Math.PI) * ringRadiusY,
    },
    data: {
      label: (
        <div className="p-2 text-xs">
          <div className="font-bold text-sm">{agent.name}</div>
          <div className="text-gray-500">{agent.tools.length} araç</div>
          <div
            className="mt-1 rounded px-1 text-white text-center"
            style={{ backgroundColor: STATUS_COLOR[agent.status] }}
          >
            {agent.status}
          </div>
          <div className="text-gray-400">güven: {(agent.trust_score * 100).toFixed(0)}%</div>
        </div>
      ),
    },
    style: {
      border: `2px solid ${STATUS_COLOR[agent.status]}`,
      borderRadius: 12,
      backgroundColor: "#1e293b",
      color: "#f1f5f9",
      width: 140,
    },
  }));

  if (showOrchestrator) {
    nodes.push({
      id: ORCHESTRATOR_ID,
      position: { x: cx, y: cy },
      data: {
        label: (
          <div className="p-2 text-xs text-center">
            <div className="font-bold text-sm">Orkestratör</div>
            <div className="text-gray-400">koordinatör</div>
          </div>
        ),
      },
      style: {
        border: `2px solid #6366f1`,
        borderRadius: 999,
        backgroundColor: "#312e81",
        color: "#f1f5f9",
        width: 130,
        boxShadow: "0 0 24px rgba(99,102,241,0.5)",
      },
    });
  }

  return { nodes, edges: [] };
}

interface Props {
  delegationEdges?: Array<{
    from: string;
    to: string;
    label?: string;
    status?: "running" | "done" | "failed";
  }>;
  showOrchestrator?: boolean;
}

const EDGE_COLOR: Record<string, string> = {
  running: "#fbbf24",
  done: "#22c55e",
  failed: "#ef4444",
};

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
      // Registry henüz ayakta değil
    }
  }, [setNodes, showOrchestrator]);

  useEffect(() => {
    loadAgents();
    const id = setInterval(loadAgents, 5000);
    return () => clearInterval(id);
  }, [loadAgents]);

  useEffect(() => {
    const dynamicEdges: Edge[] = delegationEdges.map((e, i) => {
      const color = EDGE_COLOR[e.status ?? "running"] ?? "#6366f1";
      return {
        id: `e${i}-${e.from}-${e.to}`,
        source: e.from,
        target: e.to,
        label: e.label,
        animated: e.status === "running",
        markerEnd: { type: MarkerType.ArrowClosed, color },
        style: { stroke: color, strokeWidth: e.status === "running" ? 3 : 2 },
        labelStyle: { fill: "#e2e8f0", fontSize: 11, fontWeight: 600 },
        labelBgStyle: { fill: "#0f172a" },
      };
    });
    setEdges(dynamicEdges);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(delegationEdges)]);

  return (
    <div className="h-[500px] w-full rounded-xl border border-slate-700 bg-slate-900">
      {nodes.length === 0 ? (
        <div className="flex h-full items-center justify-center text-slate-400">
          Registry bağlantısı bekleniyor…
        </div>
      ) : (
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          fitView
        >
          <Background color="#334155" gap={16} />
          <Controls />
          <MiniMap nodeColor={(n) => (n.style?.borderColor as string) ?? "#6366f1"} />
        </ReactFlow>
      )}
    </div>
  );
}
