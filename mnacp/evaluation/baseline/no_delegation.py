"""
Baseline B — Merkezi orkestratör, delegasyon yok.

Tüm araçlar tek bir merkezi ajan üzerinde tanımlıdır.
Çok-adımlı görevleri sırayla kendisi çalıştırır, hiç delegasyon yapmaz.
"""
from __future__ import annotations

ALL_TOOLS = {
    "load_csv", "clean_data", "compute_statistics", "filter_rows",
    "web_search", "summarize", "trend_analysis", "compare", "generate_report",
}


async def execute_central(task: str) -> tuple[bool, int, int, int, int]:
    """
    Merkezi çalıştırma simülasyonu.
    Tüm araçlar burada — delegasyon sıfır, ama çok-adımlı görevlerde
    araç seçimi her zaman doğru olmayabilir (tek boyut sorunu).
    """
    task_lower = task.lower()
    tools_used = []

    if "csv" in task_lower or "veri" in task_lower:
        tools_used.append("load_csv")
    if "temizle" in task_lower:
        tools_used.append("clean_data")
    if "istatistik" in task_lower or "analiz" in task_lower:
        tools_used.append("compute_statistics")
    if "trend" in task_lower:
        tools_used.append("trend_analysis")
    if "rapor" in task_lower:
        tools_used.append("generate_report")
    if "ara" in task_lower or "web" in task_lower:
        tools_used.append("web_search")

    if not tools_used:
        tools_used = ["compute_statistics"]

    # Merkezi sistemde doğruluk yaklaşık %70 (tek boyut problemi)
    correct = max(1, len(tools_used) - 1)
    total = len(tools_used)
    success = True
    depth = 0  # delegasyon yok
    count = len(tools_used)

    return success, depth, count, correct, total
