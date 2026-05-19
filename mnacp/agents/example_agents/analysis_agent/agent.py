"""Trend analizi, karşılaştırma ve raporlama ajanı."""
from __future__ import annotations

from typing import Any

from mnacp.agents.base_agent.agent import BaseAgent
from mnacp.mcp_servers.analysis_tools.tools import (
    TOOL_HANDLERS,
    CompareParams,
    CorrelationParams,
    GenerateReportParams,
    TrendAnalysisParams,
    compare,
    correlation,
    generate_report,
    trend_analysis,
)
from mnacp.protocol.schemas import ToolSchema


class AnalysisAgent(BaseAgent):
    def __init__(
        self,
        host: str = "localhost",
        port: int = 9003,
        registry_url: str = "http://localhost:8000",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            name="AnalysisAgent",
            description=(
                "Trend analizi yapan, veri setlerini karşılaştıran, korelasyon hesaplayan, "
                "markdown raporları oluşturan, sonuçları sunan ve mantık yürüten analiz ajanı. "
                "Reasoning, text_analysis, summarization, comparison, presentation, "
                "text_formatting, raporlama ve sonuç birleştirme görevleri için uygundur."
            ),
            host=host,
            port=port,
            registry_url=registry_url,
            tags=[
                "analysis", "trend", "report", "statistics", "comparison",
                "reasoning", "summarization", "text_analysis", "presentation",
                "text_formatting", "synthesis",
            ],
            **kwargs,
        )

    def define_tools(self) -> list[ToolSchema]:
        return [
            ToolSchema(
                name="trend_analysis",
                description="Zaman serisi verilerinde trend ve eğim hesaplar, hareketli ortalama döndürür",
                parameters={"values": "array", "window": "integer"},
            ),
            ToolSchema(
                name="compare",
                description="İki metrik setini karşılaştırır, değişim yüzdesi ve yönü döndürür",
                parameters={"baseline": "object", "current": "object"},
            ),
            ToolSchema(
                name="generate_report",
                description="Bölümlerden oluşan markdown veya düz metin rapor oluşturur",
                parameters={"title": "string", "sections": "array", "format": "string"},
            ),
            ToolSchema(
                name="correlation",
                description="İki sayısal dizi arasındaki Pearson korelasyon katsayısını hesaplar",
                parameters={"x": "array", "y": "array"},
            ),
        ]

    async def execute_tool(self, tool_name: str, parameters: dict[str, Any]) -> Any:
        if tool_name not in TOOL_HANDLERS:
            raise ValueError(f"AnalysisAgent: bilinmeyen araç '{tool_name}'")
        param_cls, handler = TOOL_HANDLERS[tool_name]
        params = param_cls(**parameters)
        result = handler(params)
        if hasattr(result, "__await__"):
            return await result
        return result

    async def _process_delegated_task(self, task: str, context: dict[str, Any]) -> Any:
        task_lower = task.lower()

        needs_trend = "trend" in task_lower
        needs_report = any(k in task_lower for k in ("rapor", "report", "sun", "analiz"))
        needs_compare = "karşılaştır" in task_lower or "compare" in task_lower
        needs_correlation = "korelasyon" in task_lower or "correlation" in task_lower

        if needs_compare:
            baseline = context.get("baseline", {})
            current = context.get("current", {})
            return compare(CompareParams(baseline=baseline, current=current))

        if needs_correlation:
            x = context.get("x", [])
            y = context.get("y", [])
            return correlation(CorrelationParams(x=x, y=y))

        # Trend analizi + rapor birleşimi (DataAgent peer delegasyonunda gelir)
        if needs_trend and needs_report:
            values = context.get("values", [])
            trend_result = trend_analysis(TrendAnalysisParams(values=values)) if values else None

            title = context.get("title", "Analiz Raporu")
            stats = context.get("statistics", {})
            sections = []
            if stats and isinstance(stats, dict):
                pretty = "\n".join(f"- **{k}**: {v}" for k, v in stats.items())
                sections.append({"heading": "İstatistikler", "content": pretty})
            if trend_result and isinstance(trend_result, dict):
                trend_pretty = "\n".join(f"- **{k}**: {v}" for k, v in trend_result.items())
                sections.append({"heading": "Trend Analizi", "content": trend_pretty})
            if not sections:
                sections = [{"heading": "Özet", "content": context.get("original_task", task)}]
            return generate_report(GenerateReportParams(title=title, sections=sections))

        if needs_trend:
            values = context.get("values", [])
            return trend_analysis(TrendAnalysisParams(values=values))

        if needs_report:
            title = context.get("title", "Analiz Raporu")
            previous = context.get("previous_results", {}) or {}
            sections = []
            for tid, result in previous.items():
                if isinstance(result, dict):
                    pretty = "\n".join(f"- **{k}**: {v}" for k, v in result.items())
                elif isinstance(result, list):
                    pretty = f"{len(result)} satır" + (
                        f" (örnek: {result[0]})" if result else ""
                    )
                else:
                    pretty = str(result)
                sections.append({"heading": f"Adım {tid}", "content": pretty})
            if not sections:
                sections = context.get("sections", [{"heading": "Özet", "content": context.get("original_task", "")}])
            return generate_report(GenerateReportParams(title=title, sections=sections))

        # Varsayılan: önceki sonuçlardan rapor üret
        title = context.get("title", "Analiz Raporu")
        previous = context.get("previous_results", {})
        sections = [
            {"heading": f"Adım {tid}", "content": result}
            for tid, result in previous.items()
        ] or [{"heading": "Veri", "content": str(context)}]
        return generate_report(GenerateReportParams(title=title, sections=sections))


if __name__ == "__main__":
    import asyncio
    asyncio.run(AnalysisAgent().run())
