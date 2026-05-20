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
        <label className="block text-sm font-medium text-gray-700 mb-1.5">
          Ajan rolünü doğal dille tanımla
        </label>
        <textarea
          className="w-full rounded-xl border border-gray-200 bg-white p-3 text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400 transition-all resize-none shadow-sm"
          rows={4}
          placeholder="Örn: Finansal raporları analiz eden, hisse senedi fiyatlarını takip eden bir ajan istiyorum"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>
      <button
        onClick={handleSuggest}
        disabled={loading || !description.trim()}
        className="rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-5 py-2.5 text-white font-medium hover:from-indigo-700 hover:to-violet-700 disabled:opacity-50 transition-all shadow-md shadow-indigo-200"
      >
        {loading && !proposal ? "Öneriliyor…" : "Araç Öner"}
      </button>

      {error && <p className="text-red-600 text-sm">{error}</p>}

      {proposal && (
        <div className="rounded-2xl border border-gray-200 bg-white shadow-md p-6 space-y-4 animate-slide-up">
          <div>
            <span className="text-gray-400 text-xs uppercase tracking-wide">Ajan Adı</span>
            <p className="font-semibold text-gray-900 mt-0.5">{proposal.agent_name}</p>
          </div>
          <div>
            <span className="text-gray-400 text-xs uppercase tracking-wide">Açıklama</span>
            <p className="text-gray-600 text-sm mt-0.5">{proposal.agent_description}</p>
          </div>
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-400 text-xs uppercase tracking-wide">Önerilen Araçlar</span>
              <span className="text-xs text-gray-400">
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
                    className={`flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-sm font-mono transition-all border ${
                      removed
                        ? "border-gray-200 bg-gray-50 text-gray-400 line-through"
                        : "border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-100"
                    }`}
                  >
                    {tool.name}
                    <span className={`text-xs font-bold ${removed ? "text-gray-400" : "text-indigo-500"}`}>
                      {removed ? "+" : "×"}
                    </span>
                  </button>
                );
              })}
            </div>
            <p className="text-gray-400 text-xs mt-2">Araçlara tıklayarak devre dışı bırakabilirsin.</p>
          </div>
          <div className="text-gray-400 text-xs italic border-t border-gray-100 pt-3">
            {proposal.rationale}
          </div>
          {!created ? (
            <button
              onClick={handleCreate}
              disabled={loading || removedTools.size === proposal.tools.length}
              className="rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 px-5 py-2.5 text-white font-medium hover:from-emerald-600 hover:to-teal-600 disabled:opacity-50 transition-all shadow-md shadow-emerald-100"
            >
              {loading ? "Oluşturuluyor…" : "Onayla ve Sisteme Ekle"}
            </button>
          ) : (
            <p className="text-emerald-600 font-medium">✓ Ajan başarıyla sisteme eklendi!</p>
          )}
        </div>
      )}
    </div>
  );
}
