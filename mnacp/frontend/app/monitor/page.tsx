"use client";

import Image from "next/image";
import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import DelegationFlow from "@/components/DelegationFlow";

const ORCHESTRATOR_URL =
  process.env.NEXT_PUBLIC_ORCHESTRATOR_URL || "http://localhost:8002";
const REGISTRY_URL =
  process.env.NEXT_PUBLIC_REGISTRY_URL || "http://localhost:8000";

interface Stats {
  total: number;
  completed: number;
  rejected: number;
  failed: number;
  success_rate: number;
  avg_latency_ms: number;
  avg_depth: number;
}

interface TimeseriesPoint {
  minute: string;
  count: number;
  success_count: number;
  avg_latency_ms: number;
}

interface HistoryEntry {
  request_id: string;
  from: string;
  to: string;
  task: string;
  chain_depth: number;
  status: string;
  latency_ms: number;
  timestamp: string;
}

interface AgentStats {
  agent_id: string;
  name: string;
  total: number;
  completed: number;
  failed: number;
  rejected: number;
  success_rate: number;
  avg_latency_ms: number;
  trend: "improving" | "degrading" | "stable";
}

function TrendIcon({ trend }: { trend: AgentStats["trend"] }) {
  if (trend === "improving")
    return (
      <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium bg-emerald-900/40 text-emerald-400 border border-emerald-700/30">
        ↑ iyi
      </span>
    );
  if (trend === "degrading")
    return (
      <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium bg-rose-900/40 text-rose-400 border border-rose-700/30">
        ↓ kötü
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium bg-slate-800 text-slate-500 border border-slate-700/30">
      — stabil
    </span>
  );
}

export default function MonitorPage() {
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [agentStats, setAgentStats] = useState<AgentStats[]>([]);
  const [timeseries, setTimeseries] = useState<TimeseriesPoint[]>([]);
  const [agentStatusMap, setAgentStatusMap] = useState<Record<string, string>>({});

  async function loadData() {
    try {
      const [hRes, sRes, aRes, tsRes, regRes] = await Promise.all([
        fetch(`${ORCHESTRATOR_URL}/history`),
        fetch(`${ORCHESTRATOR_URL}/stats`),
        fetch(`${ORCHESTRATOR_URL}/stats/by_agent`),
        fetch(`${ORCHESTRATOR_URL}/stats/timeseries`),
        fetch(`${REGISTRY_URL}/agents`),
      ]);
      if (hRes.ok) setHistory(await hRes.json());
      if (sRes.ok) setStats(await sRes.json());
      if (aRes.ok) setAgentStats(await aRes.json());
      if (tsRes.ok) setTimeseries(await tsRes.json());
      if (regRes.ok) {
        const agents: { agent_id: string; status: string }[] = await regRes.json();
        setAgentStatusMap(Object.fromEntries(agents.map((a) => [a.agent_id, a.status])));
      }
    } catch {
      /* servisler henüz ayakta değil */
    }
  }

  useEffect(() => {
    loadData();
    const id = setInterval(loadData, 3000);
    return () => clearInterval(id);
  }, []);

  // Latency trend serisi: son 30 delegasyon, kronolojik sıraya göre
  const latencyTrend = useMemo(() => {
    return [...history]
      .reverse()
      .slice(-30)
      .map((h, i) => ({
        index: i + 1,
        latency: Math.round(h.latency_ms),
        status: h.status,
      }));
  }, [history]);

  // Ajan bar chart için veri
  const agentChartData = useMemo(
    () =>
      agentStats.map((a) => ({
        name: a.name,
        total: a.total,
        completed: a.completed,
        failed: a.failed + a.rejected,
        avg_latency: Math.round(a.avg_latency_ms),
        success_pct: Math.round(a.success_rate * 100),
      })),
    [agentStats],
  );

  return (
    <main className="min-h-screen text-slate-100 p-8">
      <div className="max-w-6xl mx-auto space-y-8 animate-slide-up">
        <h1 className="text-2xl font-bold bg-gradient-to-r from-indigo-400 to-violet-400 bg-clip-text text-transparent">
          Delegasyon Monitörü
        </h1>

        {/* KPI kutuları */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: "Toplam", value: stats.total },
              { label: "Başarılı", value: stats.completed },
              { label: "Reddedilen", value: stats.rejected },
              {
                label: "Başarı %",
                value: `${(stats.success_rate * 100).toFixed(0)}%`,
              },
            ].map(({ label, value }) => (
              <div
                key={label}
                className="rounded-xl p-px bg-gradient-to-br from-indigo-500/40 via-violet-500/20 to-transparent"
              >
                <div className="rounded-xl bg-slate-900 p-4 text-center h-full">
                  <div className="text-2xl font-bold text-indigo-400">{value}</div>
                  <div className="text-slate-400 text-sm">{label}</div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Görev çalıştırmak için chat sayfasına yönlendirme */}
        <div className="rounded-xl border border-slate-700 bg-slate-900/40 p-4 flex items-center justify-between gap-3">
          <p className="text-sm text-slate-400">
            Görev çalıştırmak ve canlı akışı izlemek için{" "}
            <span className="text-slate-200 font-medium">Sohbet</span> sayfasını
            kullan. Bu sayfa metrik ve geçmiş izlemeye odaklıdır.
          </p>
          <a
            href="/chat"
            className="shrink-0 rounded-lg bg-indigo-600 hover:bg-indigo-500 px-4 py-2 text-sm font-semibold text-white"
          >
            Sohbete Git →
          </a>
        </div>

        {/* Ajan bazlı kırılım */}
        <section className="rounded-xl border border-slate-700 bg-slate-900/60 p-5 space-y-4">
          <div>
            <h2 className="font-semibold">Ajan Bazlı Performans</h2>
            <p className="text-xs text-slate-500 mt-1">
              Hedef ajan başına toplam çağrı, başarı oranı ve ortalama gecikme.
            </p>
          </div>
          {agentChartData.length === 0 ? (
            <div className="h-40 flex items-center justify-center text-slate-500 text-sm">
              Henüz delegasyon yok
            </div>
          ) : (
            <>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={agentChartData}>
                    <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
                    <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} />
                    <YAxis stroke="#94a3b8" fontSize={12} />
                    <Tooltip
                      contentStyle={{
                        background: "#0f172a",
                        border: "1px solid #334155",
                      }}
                    />
                    <Legend wrapperStyle={{ fontSize: "12px" }} />
                    <Bar
                      dataKey="completed"
                      stackId="a"
                      fill="#22c55e"
                      name="Başarılı"
                    />
                    <Bar
                      dataKey="failed"
                      stackId="a"
                      fill="#ef4444"
                      name="Hata/Red"
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-slate-400 text-left text-xs uppercase">
                    <tr className="border-b border-slate-700">
                      <th className="py-2">Ajan</th>
                      <th className="py-2">Toplam</th>
                      <th className="py-2">Başarılı</th>
                      <th className="py-2">Hata</th>
                      <th className="py-2">Başarı %</th>
                      <th className="py-2">Ort. Gecikme</th>
                      <th className="py-2">Trend</th>
                    </tr>
                  </thead>
                  <tbody>
                    {agentStats.map((a) => (
                      <tr
                        key={a.agent_id}
                        className="border-b border-slate-800"
                      >
                        <td className="py-2 font-medium flex items-center gap-2">
                          <span
                            className={`w-2 h-2 rounded-full shrink-0 ${
                              agentStatusMap[a.agent_id] === "online"
                                ? "bg-emerald-400"
                                : agentStatusMap[a.agent_id] === "busy"
                                ? "bg-amber-400"
                                : "bg-slate-600"
                            }`}
                            title={agentStatusMap[a.agent_id] ?? "bilinmiyor"}
                          />
                          {a.name}
                        </td>
                        <td className="py-2">{a.total}</td>
                        <td className="py-2 text-emerald-400">{a.completed}</td>
                        <td className="py-2 text-rose-400">
                          {a.failed + a.rejected}
                        </td>
                        <td className="py-2">
                          {(a.success_rate * 100).toFixed(0)}%
                        </td>
                        <td className="py-2">
                          {a.avg_latency_ms.toFixed(0)} ms
                        </td>
                        <td className="py-2 text-center">
                          <TrendIcon trend={a.trend ?? "stable"} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>

        {/* Delegasyon yoğunluğu zaman serisi */}
        <section className="rounded-xl border border-slate-700 bg-slate-900/60 p-5 space-y-3">
          <div>
            <h2 className="font-semibold">Delegasyon Yoğunluğu (Zaman Serisi)</h2>
            <p className="text-xs text-slate-500 mt-1">
              Dakika başına delegasyon sayısı ve başarı oranı.
            </p>
          </div>
          {timeseries.length === 0 ? (
            <div className="h-40 flex items-center justify-center text-slate-500 text-sm">
              Henüz veri yok
            </div>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={timeseries}>
                  <defs>
                    <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="colorSuccess" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
                  <XAxis
                    dataKey="minute"
                    stroke="#94a3b8"
                    fontSize={10}
                    tickFormatter={(v: string) => v.slice(11, 16)}
                  />
                  <YAxis stroke="#94a3b8" fontSize={12} />
                  <Tooltip
                    contentStyle={{ background: "#0f172a", border: "1px solid #334155" }}
                    labelFormatter={(v) => String(v).slice(11, 16)}
                  />
                  <Legend wrapperStyle={{ fontSize: "12px" }} />
                  <Area
                    type="monotone"
                    dataKey="count"
                    stroke="#6366f1"
                    fill="url(#colorCount)"
                    strokeWidth={2}
                    name="Toplam"
                  />
                  <Area
                    type="monotone"
                    dataKey="success_count"
                    stroke="#22c55e"
                    fill="url(#colorSuccess)"
                    strokeWidth={2}
                    name="Başarılı"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </section>

        {/* Latency trend */}
        <section className="rounded-xl border border-slate-700 bg-slate-900/60 p-5 space-y-3">
          <div>
            <h2 className="font-semibold">Gecikme Trendi (Son 30 Delegasyon)</h2>
            <p className="text-xs text-slate-500 mt-1">
              Zamansal gecikme dağılımı — yüksek nokta yavaş ajan veya karmaşık
              görev.
            </p>
          </div>
          {latencyTrend.length === 0 ? (
            <div className="h-40 flex items-center justify-center text-slate-500 text-sm">
              Henüz veri yok
            </div>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={latencyTrend}>
                  <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
                  <XAxis dataKey="index" stroke="#94a3b8" fontSize={12} />
                  <YAxis
                    stroke="#94a3b8"
                    fontSize={12}
                    label={{
                      value: "ms",
                      angle: -90,
                      position: "insideLeft",
                      fill: "#94a3b8",
                    }}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "#0f172a",
                      border: "1px solid #334155",
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="latency"
                    stroke="#6366f1"
                    strokeWidth={2}
                    dot={{ fill: "#6366f1", r: 3 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </section>

        {/* Evaluation grafikleri */}
        <section className="rounded-xl border border-slate-700 bg-slate-900/60 p-5 space-y-4">
          <div>
            <h2 className="font-semibold">
              Baseline Karşılaştırması — Akademik Değerlendirme
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              5 senaryo × 3 tekrar ile MNACP, statik atama ve merkezi (delegasyonsuz)
              baseline&apos;larla karşılaştırıldı. Statik atama: %30 ajan seçim
              doğruluğu. MNACP: %96.7.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="rounded-lg border border-slate-700 bg-slate-950 p-3">
              <div className="text-xs text-slate-400 mb-2">
                Görev Tamamlama Oranı
              </div>
              <Image
                src="/evaluation/completion_rate.png"
                alt="Görev tamamlama oranı"
                width={800}
                height={500}
                className="w-full h-auto rounded"
                unoptimized
              />
            </div>
            <div className="rounded-lg border border-slate-700 bg-slate-950 p-3">
              <div className="text-xs text-slate-400 mb-2">
                Senaryo × Sistem Heatmap
              </div>
              <Image
                src="/evaluation/scenario_heatmap.png"
                alt="Senaryo heatmap"
                width={800}
                height={500}
                className="w-full h-auto rounded"
                unoptimized
              />
            </div>
            <div className="rounded-lg border border-slate-700 bg-slate-950 p-3 md:col-span-2">
              <div className="text-xs text-slate-400 mb-2">
                Gecikme Dağılımı (P50 / P90 / P99)
              </div>
              <Image
                src="/evaluation/latency_distribution.png"
                alt="Gecikme dağılımı"
                width={1000}
                height={550}
                className="w-full h-auto rounded"
                unoptimized
              />
            </div>
          </div>
          <p className="text-[11px] text-slate-500 italic">
            Yeniden çalıştırmak için:
            <code className="ml-2 px-1 bg-slate-800 rounded text-slate-300">
              python -m mnacp.evaluation.run_evaluation --repeat 3
            </code>
          </p>
        </section>

        {/* Geçmiş tablosu */}
        <div>
          <h2 className="font-semibold mb-3">Delegasyon Geçmişi</h2>
          <DelegationFlow history={history} />
        </div>
      </div>
    </main>
  );
}
