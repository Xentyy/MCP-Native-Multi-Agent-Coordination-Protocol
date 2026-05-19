"""
Web arama araçları MCP sunucusu.
FastMCP ile her araç otomatik olarak MCP protokolüne sarılır.
"""
from __future__ import annotations

from mnacp.mcp_servers.search_tools.tools import (
    ExtractLinksParams,
    FetchPageParams,
    SummarizeParams,
    WebSearchParams,
    extract_links,
    fetch_page,
    summarize,
    web_search,
)

try:
    from fastmcp import FastMCP
    mcp = FastMCP("search-tools")

    @mcp.tool()
    async def mcp_web_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
        """Verilen sorgu için internet araması yapar ve sonuç listesi döndürür."""
        return await web_search(WebSearchParams(query=query, max_results=max_results))

    @mcp.tool()
    async def mcp_fetch_page(url: str) -> dict[str, str]:
        """Belirtilen URL'deki web sayfasının içeriğini getirir."""
        return await fetch_page(FetchPageParams(url=url))

    @mcp.tool()
    def mcp_summarize(text: str, max_sentences: int = 3) -> str:
        """Uzun metni belirli sayıda cümleye özetler."""
        return summarize(SummarizeParams(text=text, max_sentences=max_sentences))

    @mcp.tool()
    def mcp_extract_links(html: str) -> list[str]:
        """HTML içeriğinden tüm bağlantıları çıkarır."""
        return extract_links(ExtractLinksParams(html=html))

except ImportError:
    mcp = None  # fastmcp kurulu değilse HTTP katmanı yeterli


if __name__ == "__main__":
    if mcp:
        mcp.run()
    else:
        print("fastmcp kurulu değil — pip install fastmcp")
