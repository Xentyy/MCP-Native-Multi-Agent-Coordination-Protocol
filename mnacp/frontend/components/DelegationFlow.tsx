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
  completed: "bg-emerald-100 text-emerald-700 border-emerald-200",
  failed: "bg-red-100 text-red-700 border-red-200",
  rejected: "bg-amber-100 text-amber-700 border-amber-200",
  pending: "bg-blue-100 text-blue-700 border-blue-200",
  in_progress: "bg-indigo-100 text-indigo-700 border-indigo-200",
};

interface Props {
  history: DelegationEntry[];
}

export default function DelegationFlow({ history }: Props) {
  if (history.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center rounded-2xl border border-dashed border-gray-200 bg-white text-gray-400 text-sm">
        Henüz delegasyon yok
      </div>
    );
  }

  return (
    <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
      {[...history].reverse().map((entry) => (
        <div
          key={entry.request_id}
          className="rounded-xl border border-gray-200 bg-white p-3 text-sm shadow-sm hover:shadow-md transition-shadow"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="font-mono text-indigo-600 truncate max-w-[60%] text-xs">
              {entry.from.slice(0, 8)}… → {entry.to.slice(0, 8)}…
            </span>
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-medium border ${STATUS_BADGE[entry.status] ?? "bg-gray-100 text-gray-600 border-gray-200"}`}
            >
              {entry.status}
            </span>
          </div>
          <div className="mt-1 text-gray-700 truncate">{entry.task}</div>
          <div className="mt-1.5 flex gap-4 text-xs text-gray-400">
            <span>derinlik: {entry.chain_depth}</span>
            <span>{entry.latency_ms.toFixed(0)} ms</span>
            <span>{new Date(entry.timestamp).toLocaleTimeString()}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
