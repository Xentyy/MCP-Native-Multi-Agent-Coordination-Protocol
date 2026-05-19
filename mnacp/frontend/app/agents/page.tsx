"use client";

import { useEffect, useState } from "react";
import { fetchAgents, deleteGenericAgent, Agent } from "@/lib/api";

const STATUS_DOT: Record<string, string> = {
  online: "bg-green-500 shadow-green-500/50 shadow-sm",
  offline: "bg-red-500",
  busy: "bg-yellow-500",
};

function isGenericAgent(agent: Agent): boolean {
  return typeof agent.base_path === "string" && agent.base_path.startsWith("/agents/");
}

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selected, setSelected] = useState<Agent | null>(null);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    fetchAgents().then(setAgents).catch(() => setError("Registry'e erişilemiyor"));
    const id = setInterval(() => fetchAgents().then(setAgents).catch(() => {}), 5000);
    return () => clearInterval(id);
  }, []);

  async function handleDelete(agentId: string) {
    if (!confirm("Bu ajanı silmek istediğinizden emin misiniz?")) return;
    setDeleting(true);
    try {
      await deleteGenericAgent(agentId);
      setAgents((prev) => prev.filter((a) => a.agent_id !== agentId));
      setSelected(null);
    } catch {
      setError("Silme işlemi başarısız");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <main className="min-h-screen text-slate-100 p-8">
      <div className="max-w-6xl mx-auto space-y-6 animate-slide-up">
        <h1 className="text-2xl font-bold bg-gradient-to-r from-indigo-400 to-violet-400 bg-clip-text text-transparent">
          Ajan Yönetimi
        </h1>
        {error && <p className="text-red-400 text-sm">{error}</p>}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {agents.map((agent) => {
            const online = agent.status === "online";
            const active = selected?.agent_id === agent.agent_id;
            return (
              <button
                key={agent.agent_id}
                onClick={() => setSelected(agent)}
                className={`rounded-xl border p-4 text-left transition-all ${
                  active
                    ? "border-indigo-500/70 bg-slate-800/80"
                    : "border-slate-700/50 bg-slate-800/50 hover:border-indigo-500/40 hover:bg-slate-800/70"
                } backdrop-blur-sm`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span
                    className={`h-2.5 w-2.5 rounded-full flex-shrink-0 ${STATUS_DOT[agent.status] ?? "bg-slate-500"} ${online ? "shadow-sm shadow-green-500/60" : ""}`}
                  />
                  <span className="font-semibold text-slate-100 truncate">{agent.name}</span>
                  {isGenericAgent(agent) && (
                    <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded bg-violet-900/60 text-violet-300 flex-shrink-0">
                      custom
                    </span>
                  )}
                </div>
                <p className="text-slate-400 text-sm line-clamp-2">{agent.description}</p>
                <div className="flex gap-1.5 mt-2 flex-wrap">
                  {agent.tags.map((t) => (
                    <span key={t} className="rounded bg-slate-700/70 px-2 py-0.5 text-xs text-indigo-300">
                      {t}
                    </span>
                  ))}
                </div>
                {/* trust score bar */}
                <div className="mt-3">
                  <div className="flex justify-between text-xs text-slate-500 mb-1">
                    <span>Güven skoru</span>
                    <span>{(agent.trust_score * 100).toFixed(0)}%</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-slate-700">
                    <div
                      className="h-1.5 rounded-full bg-gradient-to-r from-indigo-500 to-violet-500 transition-all"
                      style={{ width: `${(agent.trust_score * 100).toFixed(0)}%` }}
                    />
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        {selected && (
          <div className="rounded-xl border border-indigo-700/50 bg-slate-800/60 backdrop-blur-sm p-6 space-y-4 animate-slide-up">
            <div className="flex justify-between items-start">
              <div>
                <h2 className="text-xl font-bold">{selected.name}</h2>
                <p className="text-slate-400 text-sm mt-0.5">{selected.host}:{selected.port}{selected.base_path || ""}</p>
              </div>
              <div className="flex items-center gap-2">
                {isGenericAgent(selected) && (
                  <button
                    onClick={() => handleDelete(selected.agent_id)}
                    disabled={deleting}
                    className="rounded-lg border border-red-700/50 bg-red-950/40 px-3 py-1.5 text-red-400 text-sm hover:bg-red-900/40 disabled:opacity-50 transition-colors"
                  >
                    {deleting ? "Siliniyor…" : "Sil"}
                  </button>
                )}
                <button
                  onClick={() => setSelected(null)}
                  className="text-slate-400 hover:text-white w-8 h-8 flex items-center justify-center rounded-lg hover:bg-slate-700"
                >
                  ✕
                </button>
              </div>
            </div>
            <p className="text-slate-300">{selected.description}</p>
            <div>
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-slate-200">Araçlar</h3>
                <span className="text-xs text-slate-500">{selected.tools.length} araç</span>
              </div>
              <div className="space-y-2">
                {selected.tools.map((tool) => (
                  <div key={tool.name} className="rounded-lg bg-slate-700/50 border border-slate-700/50 p-3">
                    <div className="font-mono text-indigo-300 text-sm">{tool.name}</div>
                    <div className="text-slate-300 text-sm mt-0.5">{tool.description}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
