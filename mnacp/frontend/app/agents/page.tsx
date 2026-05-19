"use client";

import { useEffect, useState } from "react";
import { fetchAgents, Agent } from "@/lib/api";

const STATUS_DOT: Record<string, string> = {
  online: "bg-green-500",
  offline: "bg-red-500",
  busy: "bg-yellow-500",
};

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selected, setSelected] = useState<Agent | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchAgents().then(setAgents).catch(() => setError("Registry'e erişilemiyor"));
    const id = setInterval(() => fetchAgents().then(setAgents).catch(() => {}), 5000);
    return () => clearInterval(id);
  }, []);

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-8">
      <div className="max-w-6xl mx-auto space-y-6">
        <a href="/" className="text-indigo-400 hover:underline text-sm">← Ana sayfa</a>
        <h1 className="text-2xl font-bold">Ajan Yönetimi</h1>
        {error && <p className="text-red-400">{error}</p>}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {agents.map((agent) => (
            <button
              key={agent.agent_id}
              onClick={() => setSelected(agent)}
              className={`rounded-xl border p-4 text-left transition-all ${
                selected?.agent_id === agent.agent_id
                  ? "border-indigo-500 bg-slate-700"
                  : "border-slate-700 bg-slate-800 hover:border-slate-500"
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className={`h-2.5 w-2.5 rounded-full ${STATUS_DOT[agent.status]}`} />
                <span className="font-semibold">{agent.name}</span>
              </div>
              <p className="text-slate-400 text-sm line-clamp-2">{agent.description}</p>
              <div className="flex gap-2 mt-2 flex-wrap">
                {agent.tags.map((t) => (
                  <span key={t} className="rounded bg-slate-700 px-2 py-0.5 text-xs text-indigo-300">{t}</span>
                ))}
              </div>
              <div className="mt-2 text-xs text-slate-500">
                {agent.tools.length} araç · güven {(agent.trust_score * 100).toFixed(0)}%
              </div>
            </button>
          ))}
        </div>

        {selected && (
          <div className="rounded-xl border border-indigo-700 bg-slate-800 p-6 space-y-4">
            <div className="flex justify-between items-start">
              <h2 className="text-xl font-bold">{selected.name}</h2>
              <button onClick={() => setSelected(null)} className="text-slate-400 hover:text-white">✕</button>
            </div>
            <p className="text-slate-300">{selected.description}</p>
            <div>
              <p className="text-slate-400 text-sm mb-2">Adres: {selected.host}:{selected.port}</p>
            </div>
            <div>
              <h3 className="font-semibold mb-2">Araçlar</h3>
              <div className="space-y-2">
                {selected.tools.map((tool) => (
                  <div key={tool.name} className="rounded-lg bg-slate-700 p-3">
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
