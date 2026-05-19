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
  pending: "bg-slate-700 text-slate-200",
  running: "bg-amber-600 text-amber-50 animate-pulse",
  done: "bg-emerald-600 text-emerald-50",
  failed: "bg-rose-700 text-rose-50",
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
  // edges: subtask_id → kenar; aynı subtask için sadece bir kenar tutar
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
          log(
            `Plan hazır: ${e.subtasks.length} alt görev (paralel=${e.can_parallelize})`,
            "ok",
          );
          break;
        }
        case "subtask_start":
          setSubtasks((prev) => ({
            ...prev,
            [e.subtask_id]: {
              ...prev[e.subtask_id],
              status: "running",
              agent_id: e.agent_id ?? null,
            },
          }));
          if (e.agent_id) {
            setEdges((prev) => ({
              ...prev,
              [e.subtask_id]: {
                from: "orchestrator",
                to: e.agent_id!,
                label: e.subtask_id,
                status: "running",
              },
            }));
          }
          log(`▶ ${e.description.slice(0, 70)}${e.agent_name ? ` → ${e.agent_name}` : ""}`);
          break;
        case "subtask_done":
          setSubtasks((prev) => ({
            ...prev,
            [e.subtask_id]: {
              ...prev[e.subtask_id],
              status: "done",
              agent_id: e.agent_id,
              result_preview: e.result_preview,
            },
          }));
          setEdges((prev) =>
            prev[e.subtask_id]
              ? { ...prev, [e.subtask_id]: { ...prev[e.subtask_id], status: "done" } }
              : prev,
          );
          log(`✓ tamamlandı: ${e.subtask_id.slice(0, 8)}`, "ok");
          break;
        case "subtask_failed":
          setSubtasks((prev) => ({
            ...prev,
            [e.subtask_id]: {
              ...prev[e.subtask_id],
              status: "failed",
              agent_id: e.agent_id ?? null,
              error: e.error,
            },
          }));
          setEdges((prev) =>
            prev[e.subtask_id]
              ? { ...prev, [e.subtask_id]: { ...prev[e.subtask_id], status: "failed" } }
              : prev,
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
    <main className="min-h-screen bg-slate-950 text-slate-100 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Orkestratör Sohbeti</h1>
            <p className="text-slate-400 mt-1">
              Görev gir → orkestratör ayrıştırsın, ajanlara delege etsin, sonucu canlı izle.
            </p>
          </div>
          <a href="/" className="text-indigo-400 hover:underline">← Panel</a>
        </header>

        <section className="rounded-xl border border-slate-700 bg-slate-900 p-4 space-y-3">
          <div className="flex flex-wrap gap-2">
            {PRESETS.map((p) => (
              <button
                key={p}
                onClick={() => setTask(p)}
                disabled={running}
                className="text-xs rounded-full border border-slate-700 bg-slate-800 px-3 py-1 hover:border-indigo-500 disabled:opacity-50"
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
            className="w-full h-24 rounded-lg bg-slate-800 border border-slate-700 p-3 text-sm font-mono focus:outline-none focus:border-indigo-500 disabled:opacity-50"
          />
          <div className="flex justify-between items-center">
            <div className="text-xs text-slate-500">
              {planParallel !== null && (
                <span>
                  Yürütme modu:{" "}
                  <span className="text-indigo-400 font-semibold">
                    {planParallel ? "PARALEL" : "SIRALI"}
                  </span>
                </span>
              )}
            </div>
            <div className="flex gap-2">
              {running ? (
                <button
                  onClick={onCancel}
                  className="rounded-lg bg-rose-700 hover:bg-rose-600 px-4 py-2 text-sm font-semibold"
                >
                  İptal
                </button>
              ) : (
                <button
                  onClick={onRun}
                  disabled={!task.trim()}
                  className="rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed px-5 py-2 text-sm font-semibold"
                >
                  Çalıştır
                </button>
              )}
            </div>
          </div>
        </section>

        <section>
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-lg font-semibold">Canlı Ajan Ağı</h2>
            <div className="text-xs text-slate-500">
              <span className="inline-block w-2 h-2 rounded-full bg-amber-400 mr-1" />
              çalışıyor &nbsp;
              <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 mr-1" />
              tamamlandı &nbsp;
              <span className="inline-block w-2 h-2 rounded-full bg-rose-500 mr-1" />
              başarısız
            </div>
          </div>
          <AgentGraph delegationEdges={liveEdges} showOrchestrator />
        </section>

        {error && (
          <div className="rounded-lg border border-red-800 bg-red-950 p-4 text-red-300 text-sm">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <section className="space-y-3">
            <h2 className="text-lg font-semibold">Alt Görevler</h2>
            {order.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-700 bg-slate-900/40 p-8 text-center text-slate-500 text-sm">
                Görev çalıştırınca alt görevler burada belirir.
              </div>
            ) : (
              <div className="space-y-2">
                {order.map((id) => {
                  const s = subtasks[id];
                  if (!s) return null;
                  return (
                    <div
                      key={id}
                      className="rounded-lg border border-slate-700 bg-slate-900 p-3"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium">{s.description}</div>
                          <div className="mt-1 flex flex-wrap gap-1 text-[10px]">
                            {s.required_capabilities.map((c) => (
                              <span
                                key={c}
                                className="rounded bg-slate-800 border border-slate-700 px-1.5 py-0.5 text-slate-400"
                              >
                                {c}
                              </span>
                            ))}
                            {s.depends_on.length > 0 && (
                              <span className="rounded bg-slate-800 border border-slate-700 px-1.5 py-0.5 text-amber-400">
                                ← {s.depends_on.length} bağımlılık
                              </span>
                            )}
                          </div>
                        </div>
                        <span
                          className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${STATUS_BADGE[s.status]}`}
                        >
                          {s.status}
                        </span>
                      </div>
                      {s.result_preview && (
                        <pre className="mt-2 rounded bg-slate-950 border border-slate-800 p-2 text-[11px] text-slate-300 overflow-x-auto whitespace-pre-wrap">
                          {s.result_preview}
                        </pre>
                      )}
                      {s.error && (
                        <div className="mt-2 text-xs text-rose-400">⚠ {s.error}</div>
                      )}
                      {s.agent_id && (
                        <div className="mt-1 text-[10px] text-slate-500">
                          ajan: {s.agent_id.slice(0, 8)}…
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold">Canlı Akış</h2>
            <div className="rounded-xl border border-slate-700 bg-black/60 p-3 h-72 overflow-y-auto font-mono text-xs space-y-1">
              {logs.length === 0 ? (
                <div className="text-slate-600">— Henüz olay yok —</div>
              ) : (
                logs.map((l, i) => (
                  <div
                    key={i}
                    className={
                      l.tone === "ok"
                        ? "text-emerald-400"
                        : l.tone === "err"
                          ? "text-rose-400"
                          : "text-slate-300"
                    }
                  >
                    <span className="text-slate-600">
                      [{new Date(l.ts).toLocaleTimeString()}]
                    </span>{" "}
                    {l.text}
                  </div>
                ))
              )}
            </div>

            <h2 className="text-lg font-semibold pt-2">Nihai Cevap</h2>
            {finalAnswer ? (
              <div className="rounded-xl border border-emerald-700 bg-emerald-950/30 p-4 whitespace-pre-wrap text-sm leading-relaxed">
                {finalAnswer}
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-slate-700 bg-slate-900/40 p-6 text-center text-slate-500 text-sm">
                Görev tamamlandığında cevap burada gösterilecek.
              </div>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}
