"use client";

import Image from "next/image";
import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
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
      <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
        ↑ iyi
      </span>
    );
  if (trend === "degrading")
    return (
      <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium bg-red-50 text-red-600 border border-red-200">
        ↓ kötü
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-500 border border-gray-200">
      — stabil
    </span>
  );
}

// ─── Custom tooltips ───────────────────────────────────────────────────────────
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function BarTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-lg px-4 py-3 text-sm">
      <p className="font-semibold text-gray-800 mb-1">{label}</p>
      {payload.map((p: { name: string; value: number; color: string }) => (
        <p key={p.name} style={{ color: p.color }} className="flex justify-between gap-6">
          <span>{p.name}</span>
          <span className="font-bold">{p.value}</span>
        </p>
      ))}
    </div>
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function AreaTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const time = String(label).slice(11, 16);
  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-lg px-4 py-3 text-sm">
      <p className="font-semibold text-gray-700 mb-1">{time}</p>
      {payload.map((p: { name: string; value: number; color: string }) => (
        <p key={p.name} style={{ color: p.color }} className="flex justify-between gap-6">
          <span>{p.name}</span>
          <span className="font-bold">{p.value}</span>
        </p>
      ))}
    </div>
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function LineTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-lg px-4 py-3 text-sm">
      <p className="font-semibold text-gray-700 mb-1">#{label}</p>
      {payload.map((p: { name: string; value: number; color: string }) => (
        <p key={p.name} style={{ color: p.color }} className="flex justify-between gap-6">
          <span>Gecikme</span>
          <span className="font-bold">{p.value} ms</span>
        </p>
      ))}
    </div>
  );
}

const BAR_COLORS = ["#6366f1", "#8b5cf6", "#a78bfa", "#c4b5fd", "#ddd6fe"];

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

  const latencyTrend = useMemo(() => {
    return [...history]
      .reverse()
      .slice(-30)
      .map((h, i) => ({ index: i + 1, latency: Math.round(h.latency_ms), status: h.status }));
  }, [history]);

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

  const kpiCards = stats
    ? [
        { label: "Toplam", value: stats.total, color: "text-indigo-600" },
        { label: "Başarılı", value: stats.completed, color: "text-emerald-600" },
        { label: "Reddedilen", value: stats.rejected, color: "text-amber-600" },
        { label: "Başarı %", value: `${(stats.success_rate * 100).toFixed(0)}%`, color: "text-violet-600" },
      ]
    : [];

  return (
    <main className="min-h-screen bg-slate-100 text-gray-900 p-8">
      <div className="max-w-6xl mx-auto space-y-8 animate-slide-up">
        <h1 className="text-2xl font-bold bg-gradient-to-r from-indigo-600 to-violet-600 bg-clip-text text-transparent">
          Delegasyon Monitörü
        </h1>

        {/* KPI */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {kpiCards.map(({ label, value, color }) => (
              <div key={label} className="rounded-2xl bg-white border border-gray-200 shadow-sm p-4 text-center hover:shadow-md transition-shadow">
                <div className={`text-2xl font-bold ${color}`}>{value}</div>
                <div className="text-gray-500 text-sm mt-0.5">{label}</div>
              </div>
            ))}
          </div>
        )}

        {/* Chat yönlendirme */}
        <div className="rounded-2xl border border-indigo-100 bg-indigo-50 p-4 flex items-center justify-between gap-3">
          <p className="text-sm text-gray-600">
            Görev çalıştırmak ve canlı akışı izlemek için{" "}
            <span className="text-gray-900 font-medium">Sohbet</span> sayfasını kullan.
          </p>
          <a
            href="/chat"
            className="shrink-0 rounded-xl bg-indigo-600 hover:bg-indigo-700 px-4 py-2 text-sm font-semibold text-white transition-colors"
          >
            Sohbete Git →
          </a>
        </div>

        {/* Ajan bazlı performans */}
        <section className="rounded-2xl border border-gray-200 bg-white shadow-sm p-6 space-y-4">
          <div>
            <h2 className="font-semibold text-gray-800">Ajan Bazlı Performans</h2>
            <p className="text-xs text-gray-400 mt-1">Hedef ajan başına toplam çağrı, başarı oranı ve ortalama gecikme.</p>
          </div>
          {agentChartData.length === 0 ? (
            <div className="h-40 flex items-center justify-center text-gray-400 text-sm">Henüz delegasyon yok</div>
          ) : (
            <>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={agentChartData} barCategoryGap="30%">
                    <defs>
                      <linearGradient id="gradCompleted" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#34d399" />
                        <stop offset="100%" stopColor="#059669" />
                      </linearGradient>
                      <linearGradient id="gradFailed" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#f87171" />
                        <stop offset="100%" stopColor="#dc2626" />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="#f1f5f9" strokeDasharray="4 4" />
                    <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} tickLine={false} />
                    <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                    <Tooltip content={<BarTooltip />} cursor={{ fill: "rgba(99,102,241,0.05)" }} />
                    <Legend wrapperStyle={{ fontSize: "12px", color: "#64748b" }} />
                    <Bar dataKey="completed" stackId="a" fill="url(#gradCompleted)" name="Başarılı" radius={[0, 0, 0, 0]}>
                      {agentChartData.map((_, i) => (
                        <Cell key={i} fill="url(#gradCompleted)" />
                      ))}
                    </Bar>
                    <Bar dataKey="failed" stackId="a" fill="url(#gradFailed)" name="Hata/Red" radius={[4, 4, 0, 0]}>
                      {agentChartData.map((_, i) => (
                        <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-gray-400 text-left text-xs uppercase border-b border-gray-200">
                    <tr>
                      <th className="py-2 pr-4">Ajan</th>
                      <th className="py-2 pr-4">Toplam</th>
                      <th className="py-2 pr-4">Başarılı</th>
                      <th className="py-2 pr-4">Hata</th>
                      <th className="py-2 pr-4">Başarı %</th>
                      <th className="py-2 pr-4">Ort. Gecikme</th>
                      <th className="py-2">Trend</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {agentStats.map((a) => (
                      <tr key={a.agent_id} className="hover:bg-slate-100 transition-colors">
                        <td className="py-2.5 pr-4 font-medium flex items-center gap-2">
                          <span
                            className={`w-2 h-2 rounded-full shrink-0 ${
                              agentStatusMap[a.agent_id] === "online"
                                ? "bg-emerald-500"
                                : agentStatusMap[a.agent_id] === "busy"
                                ? "bg-amber-400"
                                : "bg-gray-300"
                            }`}
                          />
                          {a.name}
                        </td>
                        <td className="py-2.5 pr-4 text-gray-600">{a.total}</td>
                        <td className="py-2.5 pr-4 text-emerald-600 font-medium">{a.completed}</td>
                        <td className="py-2.5 pr-4 text-red-500">{a.failed + a.rejected}</td>
                        <td className="py-2.5 pr-4 text-gray-700">{(a.success_rate * 100).toFixed(0)}%</td>
                        <td className="py-2.5 pr-4 text-gray-500">{a.avg_latency_ms.toFixed(0)} ms</td>
                        <td className="py-2.5">
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
        <section className="rounded-2xl border border-gray-200 bg-white shadow-sm p-6 space-y-3">
          <div>
            <h2 className="font-semibold text-gray-800">Delegasyon Yoğunluğu (Zaman Serisi)</h2>
            <p className="text-xs text-gray-400 mt-1">Dakika başına delegasyon sayısı ve başarı oranı.</p>
          </div>
          {timeseries.length === 0 ? (
            <div className="h-40 flex items-center justify-center text-gray-400 text-sm">Henüz veri yok</div>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={timeseries}>
                  <defs>
                    <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#6366f1" stopOpacity={0.35} />
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="colorSuccess" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.35} />
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#f1f5f9" strokeDasharray="4 4" />
                  <XAxis
                    dataKey="minute"
                    stroke="#94a3b8"
                    fontSize={10}
                    tickLine={false}
                    tickFormatter={(v: string) => v.slice(11, 16)}
                  />
                  <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                  <Tooltip content={<AreaTooltip />} />
                  <Legend wrapperStyle={{ fontSize: "12px", color: "#64748b" }} />
                  <Area
                    type="monotone"
                    dataKey="count"
                    stroke="#6366f1"
                    strokeWidth={2.5}
                    fill="url(#colorCount)"
                    name="Toplam"
                    animationDuration={1200}
                    dot={false}
                  />
                  <Area
                    type="monotone"
                    dataKey="success_count"
                    stroke="#10b981"
                    strokeWidth={2.5}
                    fill="url(#colorSuccess)"
                    name="Başarılı"
                    animationDuration={1200}
                    dot={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </section>

        {/* Latency trend */}
        <section className="rounded-2xl border border-gray-200 bg-white shadow-sm p-6 space-y-3">
          <div>
            <h2 className="font-semibold text-gray-800">Gecikme Trendi (Son 30 Delegasyon)</h2>
            <p className="text-xs text-gray-400 mt-1">
              Zamansal gecikme dağılımı — yüksek nokta yavaş ajan veya karmaşık görev.
            </p>
          </div>
          {latencyTrend.length === 0 ? (
            <div className="h-40 flex items-center justify-center text-gray-400 text-sm">Henüz veri yok</div>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={latencyTrend}>
                  <defs>
                    <linearGradient id="lineGrad" x1="0" y1="0" x2="1" y2="0">
                      <stop offset="0%" stopColor="#6366f1" />
                      <stop offset="100%" stopColor="#a78bfa" />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#f1f5f9" strokeDasharray="4 4" />
                  <XAxis dataKey="index" stroke="#94a3b8" fontSize={12} tickLine={false} />
                  <YAxis
                    stroke="#94a3b8"
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                    label={{ value: "ms", angle: -90, position: "insideLeft", fill: "#94a3b8", fontSize: 11 }}
                  />
                  <Tooltip content={<LineTooltip />} />
                  <Line
                    type="monotone"
                    dataKey="latency"
                    stroke="url(#lineGrad)"
                    strokeWidth={2.5}
                    dot={{ fill: "#6366f1", r: 3, strokeWidth: 0 }}
                    activeDot={{ r: 5, fill: "#6366f1" }}
                    animationDuration={1000}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </section>

        {/* Evaluation grafikleri */}
        <section className="rounded-2xl border border-gray-200 bg-white shadow-sm p-6 space-y-4">
          <div>
            <h2 className="font-semibold text-gray-800">Baseline Karşılaştırması — Akademik Değerlendirme</h2>
            <p className="text-xs text-gray-400 mt-1">
              5 senaryo × 3 tekrar ile MNACP, statik atama ve merkezi baseline&apos;larla karşılaştırıldı.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="rounded-xl border border-gray-100 bg-slate-100 p-3">
              <div className="text-xs text-gray-400 mb-2">Görev Tamamlama Oranı</div>
              <Image
                src="/evaluation/completion_rate.png"
                alt="Görev tamamlama oranı"
                width={800}
                height={500}
                className="w-full h-auto rounded"
                unoptimized
              />
            </div>
            <div className="rounded-xl border border-gray-100 bg-slate-100 p-3">
              <div className="text-xs text-gray-400 mb-2">Senaryo × Sistem Heatmap</div>
              <Image
                src="/evaluation/scenario_heatmap.png"
                alt="Senaryo heatmap"
                width={800}
                height={500}
                className="w-full h-auto rounded"
                unoptimized
              />
            </div>
            <div className="rounded-xl border border-gray-100 bg-slate-100 p-3 md:col-span-2">
              <div className="text-xs text-gray-400 mb-2">Gecikme Dağılımı (P50 / P90 / P99)</div>
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
          <p className="text-[11px] text-gray-400 italic">
            Yeniden çalıştırmak için:
            <code className="ml-2 px-1.5 py-0.5 bg-gray-100 rounded text-gray-600 font-mono text-[11px]">
              python -m mnacp.evaluation.run_evaluation --repeat 3
            </code>
          </p>
        </section>

        {/* Geçmiş */}
        <div>
          <h2 className="font-semibold mb-3 text-gray-800">Delegasyon Geçmişi</h2>
          <DelegationFlow history={history} />
        </div>
      </div>
    </main>
  );
}
