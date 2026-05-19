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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [created, setCreated] = useState(false);

  async function handleSuggest() {
    if (!description.trim()) return;
    setLoading(true);
    setError("");
    setProposal(null);
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
      const res = await fetch(`${ROLE_BUILDER_URL}/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(proposal),
      });
      if (!res.ok) throw new Error(await res.text());
      setCreated(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ajan oluşturulamadı");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-slate-300 mb-1">
          Ajan rolünü doğal dille tanımla
        </label>
        <textarea
          className="w-full rounded-lg border border-slate-600 bg-slate-800 p-3 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          rows={3}
          placeholder="Örn: Finansal raporları analiz eden, hisse senedi fiyatlarını takip eden bir ajan istiyorum"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>
      <button
        onClick={handleSuggest}
        disabled={loading || !description.trim()}
        className="rounded-lg bg-indigo-600 px-4 py-2 text-white hover:bg-indigo-500 disabled:opacity-50"
      >
        {loading ? "Öneriliyor…" : "Araç Öner"}
      </button>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {proposal && (
        <div className="rounded-xl border border-slate-700 bg-slate-800 p-4 space-y-3">
          <div>
            <span className="text-slate-400 text-xs">Ajan Adı</span>
            <p className="font-semibold text-white">{proposal.agent_name}</p>
          </div>
          <div>
            <span className="text-slate-400 text-xs">Açıklama</span>
            <p className="text-slate-200">{proposal.agent_description}</p>
          </div>
          <div>
            <span className="text-slate-400 text-xs mb-1 block">Önerilen Araçlar</span>
            <div className="space-y-2">
              {proposal.tools.map((tool) => (
                <div key={tool.name} className="rounded-lg bg-slate-700 p-2 text-sm">
                  <span className="font-mono text-indigo-300">{tool.name}</span>
                  <p className="text-slate-300 text-xs mt-0.5">{tool.description}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="text-slate-400 text-xs italic">{proposal.rationale}</div>
          {!created ? (
            <button
              onClick={handleCreate}
              disabled={loading}
              className="rounded-lg bg-green-600 px-4 py-2 text-white hover:bg-green-500 disabled:opacity-50"
            >
              {loading ? "Oluşturuluyor…" : "Onayla ve Sisteme Ekle"}
            </button>
          ) : (
            <p className="text-green-400 font-medium">✓ Ajan başarıyla sisteme eklendi!</p>
          )}
        </div>
      )}
    </div>
  );
}
