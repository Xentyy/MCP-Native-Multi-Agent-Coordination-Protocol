"""
Baseline A — Statik araç atama.

Her görev, önceden belirlenmiş tek bir ajana yönlendirilir.
Dinamik keşif veya delegasyon yoktur.
"""
from __future__ import annotations

STATIC_ROUTING: dict[str, str] = {
    "csv": "DataAgent",
    "veri": "DataAgent",
    "istatistik": "DataAgent",
    "ara": "SearchAgent",
    "web": "SearchAgent",
    "haber": "SearchAgent",
    "trend": "AnalysisAgent",
    "rapor": "AnalysisAgent",
    "karşılaştır": "AnalysisAgent",
}


def route_task(task: str) -> str:
    """Görevi anahtar kelime eşleşmesiyle statik olarak yönlendir."""
    task_lower = task.lower()
    for keyword, agent in STATIC_ROUTING.items():
        if keyword in task_lower:
            return agent
    return "DataAgent"  # varsayılan


async def execute_static(task: str) -> tuple[bool, int, int, int, int]:
    """
    Statik atama simülasyonu.
    Döndürür: (success, depth, delegation_count, correct_selections, total_selections)
    """
    agent = route_task(task)
    success = True
    depth = 0        # delegasyon yok
    count = 1        # tek atama
    correct = 1 if agent in task else 0
    total = 1
    return success, depth, count, correct, total
