"use client";

import dynamic from "next/dynamic";
import { useCallback, useMemo, useRef, useState } from "react";
import { OrchestratorEvent, streamRunTask } from "@/lib/api";

const AgentGraph = dynamic(() => import("@/components/AgentGraph"), { ssr: false });

type LiveEdge = {
  from: string;
  to: string;
  label?: string;
  status: "running" | "done" | "failed";
};

type SubtaskState = {
  id: string;
  description: string;
  required_capabilities: string[];
  depends_on: string[];
  status: "pending" | "running" | "done" | "failed";
  agent_id?: string | null;
  result_preview?: string;
  error?: string;
};

type LogLine = { ts: number; text: string; tone: "info" | "ok" | "err" };

const STATUS_BADGE: Record<SubtaskState["status"], string> = {
  pending: "bg-gray-100 text-gray-600 border border-gray-200",
  running: "bg-amber-100 text-amber-700 border border-amber-200 animate-pulse",
  done: "bg-emerald-100 text-emerald-700 border border-emerald-200",
  failed: "bg-red-100 text-red-700 border border-red-200",
};

const PRESETS = [
  "İklim değişikliğinin tarım üzerindeki etkilerini araştır ve özet çıkar.",
  "Python'da hızlı sıralama algoritmasını anlat, örnek kod ver.",
  "Yapay zeka etiği konusunda 3 temel ilke listele.",
];

export default function ChatPage() {
  const [task, setTask] = useState("");
  const [running, setRunning] = useState(false);
  const [planParallel, setPlanParallel] = useState<boolean | null>(null);
  const [subtasks, setSubtasks] = useState<Record<string, SubtaskState>>({});
  const [order, setOrder] = useState<string[]>([]);
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [finalAnswer, setFinalAnswer] = useState("");
  const [error, setError] = useState("");
  const [edges, setEdges] = useState<Record<string, LiveEdge>>({});
  const abortRef = useRef<AbortController | null>(null);

  const liveEdges = useMemo(() => Object.values(edges), [edges]);

  const log = useCallback((text: string, tone: LogLine["tone"] = "info") => {
    setLogs((prev) => [...prev, { ts: Date.now(), text, tone }]);
  }, []);

  const reset = () => {
    setSubtasks({});
    setOrder([]);
    setLogs([]);
    setFinalAnswer("");
    setError("");
    setPlanParallel(null);
    setEdges({});
  };

  const handleEvent = useCallback(
    (e: OrchestratorEvent) => {
      switch (e.type) {
        case "decompose_start":
          log(`Görev ayrıştırılıyor: ${e.task.slice(0, 80)}`);
          break;
        case "decompose_done": {
          setPlanParallel(e.can_parallelize);
          const map: Record<string, SubtaskState> = {};
          const ids: string[] = [];
          e.subtasks.forEach((s) => {
            map[s.id] = { ...s, status: "pending" };
            ids.push(s.id);
          });
          setSubtasks(map);
          setOrder(ids);
          log(`Plan hazır: ${e.subtasks.length} alt görev (paralel=${e.can_parallelize})`, "ok");
          break;
        }
        case "subtask_start":
          setSubtasks((prev) => ({
            ...prev,
            [e.subtask_id]: { ...prev[e.subtask_id], status: "running", agent_id: e.agent_id ?? null },
          }));
          if (e.agent_id) {
            setEdges((prev) => ({
              ...prev,
              [e.subtask_id]: { from: "orchestrator", to: e.agent_id!, label: e.subtask_id, status: "running" },
            }));
          }
          log(`▶ ${e.description.slice(0, 70)}${e.agent_name ? ` → ${e.agent_name}` : ""}`);
          break;
        case "subtask_done":
          setSubtasks((prev) => ({
            ...prev,
            [e.subtask_id]: { ...prev[e.subtask_id], status: "done", agent_id: e.agent_id, result_preview: e.result_preview },
          }));
          setEdges((prev) =>
            prev[e.subtask_id] ? { ...prev, [e.subtask_id]: { ...prev[e.subtask_id], status: "done" } } : prev,
          );
          log(`✓ tamamlandı: ${e.subtask_id.slice(0, 8)}`, "ok");
          break;
        case "subtask_failed":
          setSubtasks((prev) => ({
            ...prev,
            [e.subtask_id]: { ...prev[e.subtask_id], status: "failed", agent_id: e.agent_id ?? null, error: e.error },
          }));
          setEdges((prev) =>
            prev[e.subtask_id] ? { ...prev, [e.subtask_id]: { ...prev[e.subtask_id], status: "failed" } } : prev,
          );
          log(`✗ başarısız: ${e.error}`, "err");
          break;
        case "peer_delegation": {
          const edgeKey = `peer_${e.from_agent_id}_${e.to_agent_id}`;
          setEdges((prev) => ({
            ...prev,
            [edgeKey]: {
              from: e.from_agent_id,
              to: e.to_agent_id,
              label: "peer",
              status: e.status === "completed" ? "done" : e.status === "failed" ? "failed" : "running",
            },
          }));
          log(
            `⇄ Peer delegasyon: ${e.from_agent_name} → ${e.to_agent_name} (${e.status})`,
            e.status === "completed" ? "ok" : e.status === "failed" ? "err" : "info",
          );
          break;
        }
        case "aggregate_start":
          log("Sonuçlar birleştiriliyor…");
          break;
        case "final_answer":
          setFinalAnswer(e.answer);
          log("Nihai cevap hazır", "ok");
          break;
        case "error":
          setError(e.message);
          log(`Hata: ${e.message}`, "err");
          break;
      }
    },
    [log],
  );

  const onRun = async () => {
    if (!task.trim() || running) return;
    reset();
    setRunning(true);
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      await streamRunTask(task, handleEvent, ctrl.signal);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      if (msg !== "BodyStreamBuffer was aborted" && !msg.includes("aborted")) {
        setError(msg);
        log(`Bağlantı hatası: ${msg}`, "err");
      }
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  };

  const onCancel = () => {
    abortRef.current?.abort();
    setRunning(false);
    log("Kullanıcı iptal etti", "err");
  };

  return (
    <main className="min-h-screen bg-slate-100 text-gray-900 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-indigo-600 to-violet-600 bg-clip-text text-transparent">
              Orkestratör Sohbeti
            </h1>
            <p className="text-gray-500 mt-1">
              Görev gir → orkestratör ayrıştırsın, ajanlara delege etsin, sonucu canlı izle.
            </p>
          </div>
          <a href="/" className="text-indigo-600 hover:underline text-sm">← Panel</a>
        </header>

        {/* Görev girişi */}
        <section className="rounded-2xl border border-gray-200 bg-white shadow-sm p-5 space-y-3">
          <div className="flex flex-wrap gap-2">
            {PRESETS.map((p) => (
              <button
                key={p}
                onClick={() => setTask(p)}
                disabled={running}
                className="text-xs rounded-full border border-indigo-200 bg-indigo-50 text-indigo-600 px-3 py-1.5 hover:bg-indigo-100 disabled:opacity-50 transition-colors"
              >
                {p.slice(0, 40)}…
              </button>
            ))}
          </div>
          <textarea
            value={task}
            onChange={(e) => setTask(e.target.value)}
            disabled={running}
            placeholder="Bir görev yaz: 'Şu konuyu araştır ve özet çıkar', 'Şu kod parçasını analiz et' …"
            className="w-full h-24 rounded-xl bg-slate-100 border border-gray-200 p-3 text-sm font-mono focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 disabled:opacity-50 transition-all"
          />
          <div className="flex justify-between items-center">
            <div className="text-xs text-gray-400">
              {planParallel !== null && (
                <span>
                  Yürütme modu:{" "}
                  <span className="text-indigo-600 font-semibold">
                    {planParallel ? "PARALEL" : "SIRALI"}
                  </span>
                </span>
              )}
            </div>
            <div className="flex gap-2">
              {running ? (
                <button
                  onClick={onCancel}
                  className="rounded-xl bg-red-500 hover:bg-red-600 px-4 py-2 text-sm font-semibold text-white transition-colors"
                >
                  İptal
                </button>
              ) : (
                <button
                  onClick={onRun}
                  disabled={!task.trim()}
                  className="rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed px-5 py-2 text-sm font-semibold text-white transition-colors"
                >
                  Çalıştır
                </button>
              )}
            </div>
          </div>
        </section>

        {/* Canlı ajan ağı */}
        <section>
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-lg font-semibold text-gray-800">Canlı Ajan Ağı</h2>
            <div className="text-xs text-gray-400 flex items-center gap-3">
              <span className="flex items-center gap-1">
                <span className="inline-block w-2 h-2 rounded-full bg-amber-400" /> çalışıyor
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block w-2 h-2 rounded-full bg-emerald-500" /> tamamlandı
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block w-2 h-2 rounded-full bg-red-400" /> başarısız
              </span>
            </div>
          </div>
          <AgentGraph delegationEdges={liveEdges} showOrchestrator />
        </section>

        {error && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-700 text-sm">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Alt görevler */}
          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-gray-800">Alt Görevler</h2>
            {order.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-gray-200 bg-white p-8 text-center text-gray-400 text-sm">
                Görev çalıştırınca alt görevler burada belirir.
              </div>
            ) : (
              <div className="space-y-2">
                {order.map((id) => {
                  const s = subtasks[id];
                  if (!s) return null;
                  return (
                    <div key={id} className="rounded-xl border border-gray-200 bg-white p-3 shadow-sm hover:shadow-md transition-shadow">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-gray-800">{s.description}</div>
                          <div className="mt-1 flex flex-wrap gap-1 text-[10px]">
                            {s.required_capabilities.map((c) => (
                              <span key={c} className="rounded-full bg-indigo-50 border border-indigo-100 px-2 py-0.5 text-indigo-600">
                                {c}
                              </span>
                            ))}
                            {s.depends_on.length > 0 && (
                              <span className="rounded-full bg-amber-50 border border-amber-200 px-2 py-0.5 text-amber-600">
                                ← {s.depends_on.length} bağımlılık
                              </span>
                            )}
                          </div>
                        </div>
                        <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase ${STATUS_BADGE[s.status]}`}>
                          {s.status}
                        </span>
                      </div>
                      {s.result_preview && (
                        <pre className="mt-2 rounded-lg bg-slate-100 border border-gray-100 p-2 text-[11px] text-gray-600 overflow-x-auto whitespace-pre-wrap">
                          {s.result_preview}
                        </pre>
                      )}
                      {s.error && (
                        <div className="mt-2 text-xs text-red-500">⚠ {s.error}</div>
                      )}
                      {s.agent_id && (
                        <div className="mt-1 text-[10px] text-gray-400">ajan: {s.agent_id.slice(0, 8)}…</div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          {/* Canlı akış + nihai cevap */}
          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-gray-800">Canlı Akış</h2>
            <div className="rounded-xl border border-gray-200 bg-gray-900 p-3 h-72 overflow-y-auto font-mono text-xs space-y-1">
              {logs.length === 0 ? (
                <div className="text-gray-600">— Henüz olay yok —</div>
              ) : (
                logs.map((l, i) => (
                  <div
                    key={i}
                    className={
                      l.tone === "ok" ? "text-emerald-400" : l.tone === "err" ? "text-red-400" : "text-gray-300"
                    }
                  >
                    <span className="text-gray-600">[{new Date(l.ts).toLocaleTimeString()}]</span>{" "}
                    {l.text}
                  </div>
                ))
              )}
            </div>

            <h2 className="text-lg font-semibold text-gray-800 pt-2">Nihai Cevap</h2>
            {finalAnswer ? (
              <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 whitespace-pre-wrap text-sm leading-relaxed text-gray-800">
                {finalAnswer}
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-gray-200 bg-white p-6 text-center text-gray-400 text-sm">
                Görev tamamlandığında cevap burada gösterilecek.
              </div>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}
