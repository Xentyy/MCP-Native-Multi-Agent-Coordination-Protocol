"""
Analiz araçları MCP sunucusu.
FastMCP ile her araç otomatik olarak MCP protokolüne sarılır.
"""
from __future__ import annotations

from typing import Any

from mnacp.mcp_servers.analysis_tools.tools import (
    CompareParams,
    CorrelationParams,
    GenerateReportParams,
    TrendAnalysisParams,
    compare,
    correlation,
    generate_report,
    trend_analysis,
)

try:
    from fastmcp import FastMCP
    mcp = FastMCP("analysis-tools")

    @mcp.tool()
    def mcp_trend_analysis(values: list[float], window: int = 3) -> dict[str, Any]:
        """Zaman serisi verilerinde trend ve eğim hesaplar, hareketli ortalama döndürür."""
        return trend_analysis(TrendAnalysisParams(values=values, window=window))

    @mcp.tool()
    def mcp_compare(baseline: dict[str, float], current: dict[str, float]) -> dict[str, Any]:
        """İki metrik setini karşılaştırır, değişim yüzdesi ve yönü döndürür."""
        return compare(CompareParams(baseline=baseline, current=current))

    @mcp.tool()
    def mcp_generate_report(
        title: str,
        sections: list[dict[str, Any]],
        format: str = "markdown",
    ) -> str:
        """Bölümlerden oluşan markdown veya düz metin rapor oluşturur."""
        return generate_report(GenerateReportParams(title=title, sections=sections, format=format))

    @mcp.tool()
    def mcp_correlation(x: list[float], y: list[float]) -> dict[str, float]:
        """İki sayısal dizi arasındaki Pearson korelasyon katsayısını hesaplar."""
        return correlation(CorrelationParams(x=x, y=y))

except ImportError:
    mcp = None  # fastmcp kurulu değilse HTTP katmanı yeterli


if __name__ == "__main__":
    if mcp:
        mcp.run()
    else:
        print("fastmcp kurulu değil — pip install fastmcp")
