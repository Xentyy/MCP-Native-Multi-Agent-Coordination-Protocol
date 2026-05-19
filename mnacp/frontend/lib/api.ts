const REGISTRY_URL = process.env.NEXT_PUBLIC_REGISTRY_URL || "http://localhost:8000";
export const ORCHESTRATOR_URL =
  process.env.NEXT_PUBLIC_ORCHESTRATOR_URL || "http://localhost:8002";
const ROLE_BUILDER_URL =
  process.env.NEXT_PUBLIC_ROLE_BUILDER_URL || "http://localhost:8001";

export interface Agent {
  agent_id: string;
  name: string;
  description: string;
  host: string;
  port: number;
  base_path: string;
  tools: Tool[];
  status: "online" | "offline" | "busy";
  trust_score: number;
  tags: string[];
}

export interface Tool {
  name: string;
  description: string;
  parameters: Record<string, string>;
}

export interface DiscoveryResult {
  agent: Agent;
  similarity_score: number;
  matched_tools: string[];
}

export interface DelegationHistory {
  request_id: string;
  from: string;
  to: string;
  task: string;
  chain_depth: number;
  status: string;
  latency_ms: number;
  timestamp: string;
}

export async function fetchAgents(): Promise<Agent[]> {
  const res = await fetch(`${REGISTRY_URL}/agents`, { cache: "no-store" });
  if (!res.ok) throw new Error("Registry bağlantısı kurulamadı");
  return res.json();
}

export async function fetchAgent(id: string): Promise<Agent> {
  const res = await fetch(`${REGISTRY_URL}/agents/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Ajan bulunamadı");
  return res.json();
}

export async function discoverAgents(task: string): Promise<DiscoveryResult[]> {
  const res = await fetch(`${REGISTRY_URL}/discover`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task_description: task, top_k: 5 }),
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Keşif başarısız");
  return res.json();
}

export async function deleteGenericAgent(agentId: string): Promise<void> {
  const res = await fetch(`${ROLE_BUILDER_URL}/agents/${agentId}`, {
    method: "DELETE",
  });
  if (!res.ok && res.status !== 204) throw new Error("Silme başarısız");
}

export async function fetchHealth(): Promise<{ status: string; agent_count: number }> {
  const res = await fetch(`${REGISTRY_URL}/health`, { cache: "no-store" });
  if (!res.ok) throw new Error("Registry erişilemiyor");
  return res.json();
}

// ─── Orchestrator stream ────────────────────────────────────────────────────

export type OrchestratorEvent =
  | { type: "decompose_start"; task: string }
  | {
      type: "decompose_done";
      can_parallelize: boolean;
      subtasks: Array<{
        id: string;
        description: string;
        required_capabilities: string[];
        depends_on: string[];
      }>;
    }
  | {
      type: "subtask_start";
      subtask_id: string;
      description: string;
      agent_id?: string | null;
      agent_name?: string | null;
    }
  | {
      type: "subtask_done";
      subtask_id: string;
      agent_id: string | null;
      agent_name?: string | null;
      result_preview: string;
    }
  | {
      type: "subtask_failed";
      subtask_id: string;
      agent_id?: string | null;
      error: string;
    }
  | { type: "aggregate_start" }
  | { type: "final_answer"; answer: string }
  | { type: "error"; message: string }
  | {
      type: "peer_delegation";
      from_agent_id: string;
      from_agent_name: string;
      to_agent_id: string;
      to_agent_name: string;
      status: string;
    };

/**
 * Orchestrator'a görevi gönderir, SSE akışını parse edip her event için
 * verilen callback'i çağırır. fetch + ReadableStream kullanır (EventSource
 * POST desteklemiyor).
 */
export async function streamRunTask(
  task: string,
  onEvent: (e: OrchestratorEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${ORCHESTRATOR_URL}/run/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task }),
    signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(`Orchestrator hata: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const chunk = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      for (const line of chunk.split("\n")) {
        if (!line.startsWith("data:")) continue;
        const payload = line.slice(5).trim();
        if (!payload) continue;
        try {
          onEvent(JSON.parse(payload) as OrchestratorEvent);
        } catch {
          // bozuk satır — yoksay
        }
      }
    }
  }
}
