"""Veri işleme ajanı — CSV okuma, temizleme, istatistik, filtreleme."""
from __future__ import annotations

import logging
from typing import Any

from mnacp.agents.base_agent.agent import BaseAgent
from mnacp.mcp_servers.data_tools.tools import TOOL_HANDLERS, LoadCsvParams, load_csv
from mnacp.protocol.schemas import ToolSchema

logger = logging.getLogger(__name__)


def load_csv_handler(content: str) -> list[dict[str, Any]]:
    """load_csv tool fonksiyonunu çıplak çağırmak için kısa yardımcı."""
    return load_csv(LoadCsvParams(content=content))


class DataAgent(BaseAgent):
    def __init__(
        self,
        host: str = "localhost",
        port: int = 9001,
        registry_url: str = "http://localhost:8000",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            name="DataAgent",
            description=(
                "CSV dosyaları yükleyen, temizleyen, filtreleyen, dönüştüren ve "
                "istatistiksel analiz yapan veri işleme ajanı. Veri yükleme, "
                "veri temizleme, ETL, sayısal istatistik, ortalama/medyan/standart "
                "sapma hesaplama görevleri için uygundur."
            ),
            host=host,
            port=port,
            registry_url=registry_url,
            tags=[
                "data", "csv", "statistics", "etl", "data_cleaning",
                "data_transformation", "numerical_analysis", "load_csv",
                "compute_statistics", "filter_rows", "clean_data",
            ],
            **kwargs,
        )

    def define_tools(self) -> list[ToolSchema]:
        return [
            ToolSchema(
                name="load_csv",
                description="CSV metin içeriğini satır listesine dönüştürür",
                parameters={"content": "string", "delimiter": "string"},
            ),
            ToolSchema(
                name="clean_data",
                description="Boş ve kirli verileri satır listesinden temizler",
                parameters={"rows": "array", "drop_empty": "boolean", "strip_whitespace": "boolean"},
            ),
            ToolSchema(
                name="compute_statistics",
                description="Belirtilen sütun için ortalama, medyan, standart sapma hesaplar",
                parameters={"rows": "array", "column": "string"},
            ),
            ToolSchema(
                name="filter_rows",
                description="Satırları belirtilen koşula göre filtreler (eq, neq, gt, lt, contains)",
                parameters={"rows": "array", "column": "string", "value": "string", "operator": "string"},
            ),
        ]

    async def execute_tool(self, tool_name: str, parameters: dict[str, Any]) -> Any:
        if tool_name not in TOOL_HANDLERS:
            raise ValueError(f"DataAgent: bilinmeyen araç '{tool_name}'")
        param_cls, handler = TOOL_HANDLERS[tool_name]
        params = param_cls(**parameters)
        result = handler(params)
        # Async handler varsa bekle
        if hasattr(result, "__await__"):
            return await result
        return result

    @staticmethod
    def _extract_csv_block(text: str) -> str | None:
        """Serbest metinden CSV bloğunu yakala.

        Strateji: tüm metni satırlara böl, başlık olarak SADECE virgülle
        ayrılmış SAF satırları (cümle eki olmayan, ':' içermeyen, tüm
        hücreleri kısa tek-kelime/sayı olan) düşün. Ardışık tutarlı
        satırları topla.
        """
        if not text:
            return None

        def is_csv_line(line: str) -> bool:
            if "," not in line or ":" in line:
                return False
            cells = [c.strip() for c in line.split(",")]
            if len(cells) < 2:
                return False
            # Hücreler kısa olsun, içlerinde boşluk az olsun (cümle değil)
            for c in cells:
                if not c or len(c) > 40 or c.count(" ") > 1:
                    return False
            return True

        all_lines = [ln.rstrip() for ln in text.splitlines()]
        for i, line in enumerate(all_lines):
            if not is_csv_line(line):
                continue
            cols = line.count(",") + 1
            block = [line]
            for nxt in all_lines[i + 1:]:
                if is_csv_line(nxt) and nxt.count(",") + 1 == cols:
                    block.append(nxt)
                elif nxt.strip() == "":
                    continue
                else:
                    break
            if len(block) >= 2:
                return "\n".join(block)
        return None

    @staticmethod
    def _rows_from_previous(previous: dict[str, Any]) -> list[dict[str, Any]]:
        """Önceki sonuçlar arasında list[dict] tipinde olanı bul."""
        for v in previous.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
        return []

    @staticmethod
    def _normalize(s: str) -> str:
        """Türkçe karakter normalizasyonu: maaş/maas eşit sayılsın."""
        m = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
        return s.translate(m).lower()

    @staticmethod
    def _pick_numeric_column(rows: list[dict[str, Any]], hint: str = "") -> str | None:
        if not rows:
            return None
        hint_n = DataAgent._normalize(hint)
        # 1) İpucuyla eşleşen sayısal sütun
        for col in rows[0].keys():
            col_n = DataAgent._normalize(col)
            if col_n and col_n in hint_n:
                if all(DataAgent._can_be_float(r.get(col)) for r in rows):
                    return col
        # 2) İlk sayısal sütun
        for col in rows[0].keys():
            if all(DataAgent._can_be_float(r.get(col)) for r in rows):
                return col
        return None

    @staticmethod
    def _can_be_float(v: Any) -> bool:
        try:
            float(v)
            return True
        except (TypeError, ValueError):
            return False

    async def _process_delegated_task(self, task: str, context: dict[str, Any]) -> Any:
        """Görev açıklamasına göre en uygun aracı seç ve çalıştır.

        Context öncelik sırası: doğrudan parametreler > previous_results >
        original_task içine gömülü CSV.

        Hem istatistik hem rapor/analiz isteniyorsa: istatistiği yerel hesapla,
        ardından AnalysisAgent'a peer delegasyon yap. Sonuç _peer_delegations
        alanıyla birlikte döndürülür; orkestratör bunu SSE event'e çevirir.
        """
        task_lower = task.lower()
        original_task = context.get("original_task", "")
        combined = (task_lower + " " + original_task.lower())
        previous = context.get("previous_results", {}) or {}

        needs_stats = any(k in combined for k in (
            "istatistik", "statistic", "ortalama", "standart", "mean", "stdev", "stddev",
        ))
        needs_analysis = any(k in combined for k in (
            "rapor", "report", "analiz", "analysis", "trend", "karşılaştır", "compare",
            "özet", "summary", "sunum",
        ))

        # rows kaynağı: context.rows > previous_results > original_task'ı yükle
        def _resolve_rows() -> list[dict[str, Any]]:
            if context.get("rows"):
                return context["rows"]
            prev_rows = self._rows_from_previous(previous)
            if prev_rows:
                return prev_rows
            csv_block = self._extract_csv_block(original_task)
            if csv_block:
                return load_csv_handler(csv_block)
            return []

        if "yükle" in task_lower or "load" in task_lower or "oku" in task_lower or "csv" in task_lower:
            content = (
                context.get("csv_content")
                or context.get("content")
                or self._extract_csv_block(original_task)
                or ""
            )
            if not content:
                return {"error": "CSV içeriği bulunamadı"}
            return await self.execute_tool("load_csv", {"content": content})

        if "temizle" in task_lower or "clean" in task_lower:
            rows = _resolve_rows()
            return await self.execute_tool("clean_data", {"rows": rows})

        if needs_stats:
            rows = _resolve_rows()
            column = context.get("column") or DataAgent._pick_numeric_column(rows, task)
            if not rows or not column:
                return {"error": "İstatistik için sayısal sütun bulunamadı", "rows_count": len(rows)}
            stats_result = await self.execute_tool("compute_statistics", {"rows": rows, "column": column})

            if needs_analysis:
                peer_result = await self._delegate_to_peer(
                    task="İstatistik verilerinden trend analizi ve rapor oluştur",
                    context=context,
                    required_capabilities=["generate_report", "trend_analysis"],
                    peer_context={
                        "values": [float(r.get(column, 0)) for r in rows if self._can_be_float(r.get(column))],
                        "statistics": stats_result,
                        "column": column,
                        "title": f"{column} Sütunu Analiz Raporu",
                    },
                )
                return {
                    "statistics": stats_result,
                    "analysis": peer_result.get("result") if peer_result else None,
                    "_peer_delegations": [peer_result] if peer_result else [],
                }
            return stats_result

        if "filtre" in task_lower or "filter" in task_lower:
            rows = _resolve_rows()
            return await self.execute_tool("filter_rows", {
                "rows": rows,
                "column": context.get("column", ""),
                "value": context.get("value", ""),
                "operator": context.get("operator", "eq"),
            })

        # Varsayılan: rows varsa istatistik, yoksa CSV yükle
        rows = _resolve_rows()
        if rows:
            column = DataAgent._pick_numeric_column(rows)
            if column:
                stats_result = await self.execute_tool("compute_statistics", {"rows": rows, "column": column})
                if needs_analysis:
                    peer_result = await self._delegate_to_peer(
                        task="İstatistik verilerinden trend analizi ve rapor oluştur",
                        context=context,
                        required_capabilities=["generate_report", "trend_analysis"],
                        peer_context={
                            "values": [float(r.get(column, 0)) for r in rows if self._can_be_float(r.get(column))],
                            "statistics": stats_result,
                            "column": column,
                            "title": f"{column} Sütunu Analiz Raporu",
                        },
                    )
                    return {
                        "statistics": stats_result,
                        "analysis": peer_result.get("result") if peer_result else None,
                        "_peer_delegations": [peer_result] if peer_result else [],
                    }
                return stats_result
            return rows
        return {"message": "Çalıştırılacak görev veya veri bulunamadı"}



if __name__ == "__main__":
    import asyncio
    asyncio.run(DataAgent().run())
