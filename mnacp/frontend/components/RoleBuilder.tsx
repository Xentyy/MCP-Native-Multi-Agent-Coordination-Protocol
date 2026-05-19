"use client";

import { useState } from "react";

interface ToolProposal {
  name: string;
  description: string;
  parameters: Record<string, string>;
}

interface RoleProposal {
  agent_name: string;
  agent_description: string;
  tags: string[];
  tools: ToolProposal[];
  rationale: string;
}

const ROLE_BUILDER_URL =
  process.env.NEXT_PUBLIC_ROLE_BUILDER_URL || "http://localhost:8001";

export default function RoleBuilder() {
  const [description, setDescription] = useState("");
  const [proposal, setProposal] = useState<RoleProposal | null>(null);
  const [removedTools, setRemovedTools] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [created, setCreated] = useState(false);

  async function handleSuggest() {
    if (!description.trim()) return;
    setLoading(true);
    setError("");
    setProposal(null);
    setRemovedTools(new Set());
    setCreated(false);
    try {
      const res = await fetch(`${ROLE_BUILDER_URL}/suggest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ description }),
      });
      if (!res.ok) throw new Error(await res.text());
      setProposal(await res.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Öneri alınamadı");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate() {
    if (!proposal) return;
    setLoading(true);
    try {
      const activeTools = proposal.tools.filter((t) => !removedTools.has(t.name));
      const res = await fetch(`${ROLE_BUILDER_URL}/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...proposal, tools: activeTools }),
      });
      if (!res.ok) throw new Error(await res.text());
      setCreated(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ajan oluşturulamadı");
    } finally {
      setLoading(false);
    }
  }

  function toggleTool(name: string) {
    setRemovedTools((prev) => {
      const next = new Set(prev);
      if (next.has(name)) { next.delete(name); } else { next.add(name); }
      return next;
    });
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-slate-300 mb-1.5">
          Ajan rolünü doğal dille tanımla
        </label>
        <textarea
          className="w-full rounded-xl border border-slate-700/60 bg-slate-800/60 backdrop-blur-sm p-3 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50 transition-colors resize-none"
          rows={4}
          placeholder="Örn: Finansal raporları analiz eden, hisse senedi fiyatlarını takip eden bir ajan istiyorum"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>
      <button
        onClick={handleSuggest}
        disabled={loading || !description.trim()}
        className="rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-5 py-2 text-white font-medium hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 transition-all shadow-lg shadow-indigo-900/30"
      >
        {loading && !proposal ? "Öneriliyor…" : "Araç Öner"}
      </button>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {proposal && (
        <div className="rounded-xl border border-slate-700/50 bg-slate-800/60 backdrop-blur-sm p-5 space-y-4 animate-slide-up">
          <div>
            <span className="text-slate-500 text-xs uppercase tracking-wide">Ajan Adı</span>
            <p className="font-semibold text-white mt-0.5">{proposal.agent_name}</p>
          </div>
          <div>
            <span className="text-slate-500 text-xs uppercase tracking-wide">Açıklama</span>
            <p className="text-slate-200 text-sm mt-0.5">{proposal.agent_description}</p>
          </div>
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-slate-500 text-xs uppercase tracking-wide">Önerilen Araçlar</span>
              <span className="text-xs text-slate-500">
                {proposal.tools.length - removedTools.size}/{proposal.tools.length} seçili
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              {proposal.tools.map((tool) => {
                const removed = removedTools.has(tool.name);
                return (
                  <button
                    key={tool.name}
                    type="button"
                    title={tool.description}
                    onClick={() => toggleTool(tool.name)}
                    className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-mono transition-all border ${
                      removed
                        ? "border-slate-700/40 bg-slate-800/30 text-slate-600 line-through"
                        : "border-indigo-500/30 bg-indigo-900/30 text-indigo-300 hover:bg-indigo-900/50"
                    }`}
                  >
                    {tool.name}
                    <span className={`text-xs ${removed ? "text-slate-600" : "text-indigo-500"}`}>
                      {removed ? "+" : "×"}
                    </span>
                  </button>
                );
              })}
            </div>
            <p className="text-slate-500 text-xs mt-2">Araçlara tıklayarak devre dışı bırakabilirsin.</p>
          </div>
          <div className="text-slate-400 text-xs italic border-t border-slate-700/40 pt-3">
            {proposal.rationale}
          </div>
          {!created ? (
            <button
              onClick={handleCreate}
              disabled={loading || removedTools.size === proposal.tools.length}
              className="rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 px-5 py-2 text-white font-medium hover:from-emerald-500 hover:to-teal-500 disabled:opacity-50 transition-all shadow-lg shadow-emerald-900/30"
            >
              {loading ? "Oluşturuluyor…" : "Onayla ve Sisteme Ekle"}
            </button>
          ) : (
            <p className="text-emerald-400 font-medium">✓ Ajan başarıyla sisteme eklendi!</p>
          )}
        </div>
      )}
    </div>
  );
}
