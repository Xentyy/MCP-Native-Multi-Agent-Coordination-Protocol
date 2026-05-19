"""
Veri araçları MCP sunucusu.
FastMCP ile her araç otomatik olarak MCP protokolüne sarılır.
"""
from __future__ import annotations

from typing import Any

from mnacp.mcp_servers.data_tools.tools import (
    CleanDataParams,
    ComputeStatisticsParams,
    FilterRowsParams,
    LoadCsvParams,
    clean_data,
    compute_statistics,
    filter_rows,
    load_csv,
)

try:
    from fastmcp import FastMCP
    mcp = FastMCP("data-tools")

    @mcp.tool()
    def mcp_load_csv(content: str, delimiter: str = ",") -> list[dict[str, Any]]:
        """CSV metin içeriğini satır listesine dönüştürür."""
        return load_csv(LoadCsvParams(content=content, delimiter=delimiter))

    @mcp.tool()
    def mcp_clean_data(
        rows: list[dict[str, Any]],
        drop_empty: bool = True,
        strip_whitespace: bool = True,
    ) -> list[dict[str, Any]]:
        """Satır listesindeki boş ve kirli verileri temizler."""
        return clean_data(CleanDataParams(rows=rows, drop_empty=drop_empty, strip_whitespace=strip_whitespace))

    @mcp.tool()
    def mcp_compute_statistics(rows: list[dict[str, Any]], column: str) -> dict[str, float]:
        """Belirtilen sütun için temel istatistikleri hesaplar."""
        return compute_statistics(ComputeStatisticsParams(rows=rows, column=column))

    @mcp.tool()
    def mcp_filter_rows(
        rows: list[dict[str, Any]],
        column: str,
        value: str,
        operator: str = "eq",
    ) -> list[dict[str, Any]]:
        """Belirtilen koşula göre satırları filtreler."""
        return filter_rows(FilterRowsParams(rows=rows, column=column, value=value, operator=operator))

except ImportError:
    mcp = None  # fastmcp kurulu değilse HTTP katmanı yeterli


if __name__ == "__main__":
    if mcp:
        mcp.run()
    else:
        print("fastmcp kurulu değil — pip install fastmcp")
