"use client";


interface DelegationEntry {
  request_id: string;
  from: string;
  to: string;
  task: string;
  chain_depth: number;
  status: string;
  latency_ms: number;
  timestamp: string;
}

const STATUS_BADGE: Record<string, string> = {
  completed: "bg-green-600",
  failed: "bg-red-600",
  rejected: "bg-yellow-600",
  pending: "bg-blue-600",
  in_progress: "bg-indigo-600",
};

interface Props {
  history: DelegationEntry[];
}

export default function DelegationFlow({ history }: Props) {
  if (history.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center rounded-xl border border-slate-700 bg-slate-900 text-slate-400">
        Henüz delegasyon yok
      </div>
    );
  }

  return (
    <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
      {[...history].reverse().map((entry) => (
        <div
          key={entry.request_id}
          className="rounded-lg border border-slate-700 bg-slate-800 p-3 text-sm"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="font-mono text-indigo-400 truncate max-w-[60%]">
              {entry.from.slice(0, 8)}… → {entry.to.slice(0, 8)}…
            </span>
            <span
              className={`rounded px-2 py-0.5 text-xs text-white ${STATUS_BADGE[entry.status] ?? "bg-slate-600"}`}
            >
              {entry.status}
            </span>
          </div>
          <div className="mt-1 text-slate-300 truncate">{entry.task}</div>
          <div className="mt-1 flex gap-4 text-xs text-slate-500">
            <span>derinlik: {entry.chain_depth}</span>
            <span>{entry.latency_ms.toFixed(0)} ms</span>
            <span>{new Date(entry.timestamp).toLocaleTimeString()}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
