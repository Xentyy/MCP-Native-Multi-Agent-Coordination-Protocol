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

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-8">
      <div className="max-w-6xl mx-auto space-y-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white">MNACP Dashboard</h1>
            <p className="text-slate-400 mt-1">Multi-Agent Coordination Protocol — Canlı İzleme</p>
          </div>
          {health && (
            <div className="rounded-xl border border-slate-700 bg-slate-800 px-4 py-2 text-right">
              <div className="text-green-400 font-semibold">{health.status.toUpperCase()}</div>
              <div className="text-slate-400 text-sm">{health.agent_count} ajan aktif</div>
            </div>
          )}
        </div>

        {error && (
          <div className="rounded-lg border border-red-800 bg-red-950 p-4 text-red-300">
            {error}
          </div>
        )}

        <div className="grid grid-cols-3 gap-4">
          {[
            { label: "Toplam Ajan", value: agents.length },
            { label: "Çevrimiçi", value: agents.filter((a) => a.status === "online").length },
            { label: "Toplam Araç", value: agents.reduce((s, a) => s + a.tools.length, 0) },
          ].map(({ label, value }) => (
            <div key={label} className="rounded-xl border border-slate-700 bg-slate-800 p-5 text-center">
              <div className="text-4xl font-bold text-indigo-400">{value}</div>
              <div className="text-slate-400 mt-1">{label}</div>
            </div>
          ))}
        </div>

        <div>
          <h2 className="text-xl font-semibold mb-3">Ajan Ağı</h2>
          <AgentGraph />
        </div>

        <nav className="flex flex-wrap gap-4 text-indigo-400">
          <a href="/chat" className="hover:underline">→ Orkestratör Sohbeti</a>
          <a href="/agents" className="hover:underline">→ Ajan Yönetimi</a>
          <a href="/roles" className="hover:underline">→ Rol Oluşturucu</a>
          <a href="/monitor" className="hover:underline">→ Delegasyon Monitörü</a>
        </nav>
      </div>
    </main>
  );
}
