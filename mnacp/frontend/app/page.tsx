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
    { label: "Toplam Ajan", value: agents.length, color: "from-indigo-500 to-indigo-600" },
    { label: "Çevrimiçi", value: agents.filter((a) => a.status === "online").length, color: "from-emerald-500 to-emerald-600" },
    { label: "Toplam Araç", value: agents.reduce((s, a) => s + a.tools.length, 0), color: "from-violet-500 to-violet-600" },
  ];

  return (
    <main className="min-h-screen bg-slate-100 text-gray-900 p-8">
      <div className="max-w-6xl mx-auto space-y-8 animate-slide-up">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-indigo-600 via-violet-600 to-purple-600 bg-clip-text text-transparent">
              MNACP Dashboard
            </h1>
            <p className="text-gray-500 mt-1">Multi-Agent Coordination Protocol — Canlı İzleme</p>
          </div>
          {health && (
            <div className="flex items-center gap-2 rounded-xl border border-gray-200 bg-white shadow-sm px-4 py-2">
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
              </span>
              <div className="text-right">
                <div className="text-emerald-600 font-semibold text-sm">{health.status.toUpperCase()}</div>
                <div className="text-gray-400 text-xs">{health.agent_count} ajan aktif</div>
              </div>
            </div>
          )}
        </div>

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-700 text-sm">
            {error}
          </div>
        )}

        {/* KPI kartlar */}
        <div className="grid grid-cols-3 gap-4">
          {kpis.map(({ label, value, color }) => (
            <div key={label} className="rounded-2xl bg-white border border-gray-200 shadow-sm p-5 flex flex-col items-center gap-1 hover:shadow-md transition-shadow">
              <div className={`text-4xl font-bold bg-gradient-to-br ${color} bg-clip-text text-transparent`}>{value}</div>
              <div className="text-gray-500 text-sm">{label}</div>
            </div>
          ))}
        </div>

        {/* Ajan ağı */}
        <div>
          <h2 className="text-xl font-semibold mb-3 text-gray-800">Ajan Ağı</h2>
          <AgentGraph />
        </div>
      </div>
    </main>
  );
}
