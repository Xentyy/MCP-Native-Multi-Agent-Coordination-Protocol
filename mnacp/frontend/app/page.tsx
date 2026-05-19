"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { fetchHealth, fetchAgents, Agent } from "@/lib/api";

const AgentGraph = dynamic(() => import("@/components/AgentGraph"), { ssr: false });

export default function Home() {
  const [health, setHealth] = useState<{ status: string; agent_count: number } | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const [h, a] = await Promise.all([fetchHealth(), fetchAgents()]);
        setHealth(h);
        setAgents(a);
      } catch {
        setError("Registry bağlantısı kurulamadı (localhost:8000)");
      }
    }
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, []);

  const kpis = [
    { label: "Toplam Ajan", value: agents.length },
    { label: "Çevrimiçi", value: agents.filter((a) => a.status === "online").length },
    { label: "Toplam Araç", value: agents.reduce((s, a) => s + a.tools.length, 0) },
  ];

  return (
    <main className="min-h-screen text-slate-100 p-8">
      <div className="max-w-6xl mx-auto space-y-8 animate-slide-up">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-indigo-400 via-violet-400 to-purple-400 bg-clip-text text-transparent">
              MNACP Dashboard
            </h1>
            <p className="text-slate-400 mt-1">Multi-Agent Coordination Protocol — Canlı İzleme</p>
          </div>
          {health && (
            <div className="flex items-center gap-2 rounded-xl border border-slate-700/50 bg-slate-800/60 backdrop-blur-sm px-4 py-2">
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500" />
              </span>
              <div className="text-right">
                <div className="text-green-400 font-semibold text-sm">{health.status.toUpperCase()}</div>
                <div className="text-slate-400 text-xs">{health.agent_count} ajan aktif</div>
              </div>
            </div>
          )}
        </div>

        {error && (
          <div className="rounded-lg border border-red-800 bg-red-950/50 p-4 text-red-300">
            {error}
          </div>
        )}

        {/* KPI kartları — gradient border trick */}
        <div className="grid grid-cols-3 gap-4">
          {kpis.map(({ label, value }) => (
            <div
              key={label}
              className="rounded-xl p-px bg-gradient-to-br from-indigo-500/40 via-violet-500/20 to-transparent"
            >
              <div className="rounded-xl bg-slate-900 p-5 text-center h-full">
                <div className="text-4xl font-bold text-indigo-400">{value}</div>
                <div className="text-slate-400 mt-1 text-sm">{label}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Ajan ağı */}
        <div>
          <h2 className="text-xl font-semibold mb-3 text-slate-200">Ajan Ağı</h2>
          <AgentGraph />
        </div>
      </div>
    </main>
  );
}
