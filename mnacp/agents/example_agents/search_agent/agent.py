"""Web arama ve içerik özetleme ajanı — gerçek DuckDuckGo araması."""
from __future__ import annotations

import logging
from typing import Any

from mnacp.agents.base_agent.agent import BaseAgent
from mnacp.mcp_servers.search_tools.tools import (
    TOOL_HANDLERS,
    FetchPageParams,
    SummarizeParams,
    WebSearchParams,
    fetch_page,
    summarize,
    web_search,
)
from mnacp.protocol.delegation import DelegationManager
from mnacp.protocol.discovery import DiscoveryProtocol
from mnacp.protocol.schemas import DelegationStatus, ToolSchema

logger = logging.getLogger(__name__)


class SearchAgent(BaseAgent):
    def __init__(
        self,
        host: str = "localhost",
        port: int = 9002,
        registry_url: str = "http://localhost:8000",
        **kwargs: Any,
    ) -> None:
        self._delegation_mgr = DelegationManager(max_depth=5)
        self._discovery = DiscoveryProtocol(registry_url)
        super().__init__(
            name="SearchAgent",
            description=(
                "Gerçek web aramalarıyla bilgi toplayan araştırma ajanı. DuckDuckGo üzerinden "
                "güncel haber, makale ve kaynak arar; sayfa içeriği getirir ve özetler. "
                "Araştırma (research), literatür taraması, bilgi toplama, kaynak doğrulama, "
                "web search, haberler, güncel olaylar, dış kaynaklı veri toplama için kullanılır."
            ),
            host=host,
            port=port,
            registry_url=registry_url,
            tags=[
                "search", "research", "web", "scraping", "summarization",
                "literature_review", "knowledge", "sources", "fact_check",
                "news", "current_events", "web_search",
            ],
            **kwargs,
        )

    def define_tools(self) -> list[ToolSchema]:
        return [
            ToolSchema(
                name="web_search",
                description="DuckDuckGo üzerinden gerçek internet araması yapar ve sonuç listesi döndürür",
                parameters={"query": "string", "max_results": "integer"},
            ),
            ToolSchema(
                name="fetch_page",
                description="Belirtilen URL'deki web sayfasının içeriğini getirir ve düz metne çevirir",
                parameters={"url": "string"},
            ),
            ToolSchema(
                name="summarize",
                description="Uzun metni belirli sayıda cümleye özetler",
                parameters={"text": "string", "max_sentences": "integer"},
            ),
            ToolSchema(
                name="extract_links",
                description="HTML içeriğinden tüm bağlantıları çıkarır",
                parameters={"html": "string"},
            ),
        ]

    async def execute_tool(self, tool_name: str, parameters: dict[str, Any]) -> Any:
        if tool_name not in TOOL_HANDLERS:
            raise ValueError(f"SearchAgent: bilinmeyen araç '{tool_name}'")
        param_cls, handler = TOOL_HANDLERS[tool_name]
        params = param_cls(**parameters)
        result = handler(params)
        if hasattr(result, "__await__"):
            return await result
        return result

    async def _process_delegated_task(self, task: str, context: dict[str, Any]) -> Any:
        task_lower = task.lower()
        original_task = context.get("original_task", task)
        combined = task_lower + " " + original_task.lower()

        needs_analysis = any(k in combined for k in (
            "analiz", "analysis", "rapor", "report", "trend",
            "karşılaştır", "compare", "özet", "summary",
        ))

        search_result: dict[str, Any] | None = None

        # Arama görevi
        if any(k in task_lower for k in ("ara", "search", "bul", "araştır", "research", "bilgi", "haber")):
            query = context.get("query") or _extract_query(task, original_task)
            max_results = int(context.get("max_results", 5))
            results = await web_search(WebSearchParams(query=query, max_results=max_results))

            if not results or (len(results) == 1 and results[0].get("title") == "Arama hatası"):
                return {"search_results": [], "summary": "Arama başarısız", "query": query}

            page_content = ""
            first_url = next((r["url"] for r in results if r.get("url", "").startswith("http")), "")
            if first_url:
                try:
                    page = await fetch_page(FetchPageParams(url=first_url))
                    page_content = page.get("content", "")[:3000]
                except Exception:
                    pass

            combined_text = " ".join(r.get("snippet", "") for r in results if r.get("snippet"))
            if page_content:
                combined_text = page_content + " " + combined_text
            summary = summarize(SummarizeParams(text=combined_text, max_sentences=5)) if combined_text else ""

            search_result = {
                "query": query,
                "search_results": results[:max_results],
                "page_preview": page_content[:1000] if page_content else "",
                "summary": summary,
            }

            # Analiz/rapor da isteniyorsa AnalysisAgent'a peer delegasyon yap
            if needs_analysis:
                peer_result = await self._delegate_to_analysis_agent(
                    task=task,
                    search_data=search_result,
                    context=context,
                )
                if peer_result:
                    search_result["analysis"] = peer_result.get("result")
                    search_result["_peer_delegations"] = [peer_result]

            return search_result

        # Sayfa getirme
        if any(k in task_lower for k in ("fetch", "getir", "sayfa", "url", "link")):
            url = context.get("url", "")
            if not url:
                import re
                m = re.search(r"https?://\S+", task)
                url = m.group(0) if m else ""
            if not url:
                return {"error": "URL bulunamadı"}
            page = await fetch_page(FetchPageParams(url=url))
            if page.get("content"):
                page["summary"] = summarize(SummarizeParams(text=page["content"], max_sentences=5))
            return page

        # Özetleme
        if any(k in task_lower for k in ("özetle", "summarize", "özet")):
            text = context.get("text", task)
            n = int(context.get("max_sentences", 5))
            return summarize(SummarizeParams(text=text, max_sentences=n))

        # Varsayılan: araştır
        query = context.get("query") or _extract_query(task, original_task)
        results = await web_search(WebSearchParams(query=query, max_results=5))
        combined_text = " ".join(r.get("snippet", "") for r in results if r.get("snippet"))
        summary = summarize(SummarizeParams(text=combined_text, max_sentences=5)) if combined_text else ""
        search_result = {"query": query, "search_results": results, "summary": summary}

        if needs_analysis:
            peer_result = await self._delegate_to_analysis_agent(
                task=task,
                search_data=search_result,
                context=context,
            )
            if peer_result:
                search_result["analysis"] = peer_result.get("result")
                search_result["_peer_delegations"] = [peer_result]

        return search_result

    async def _delegate_to_analysis_agent(
        self,
        task: str,
        search_data: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Arama sonuçlarını analiz/rapor için AnalysisAgent'a peer delegasyon yapar."""
        try:
            candidate = await self._discovery.find_best_agent(
                task="arama sonuçlarını analiz et ve rapor oluştur",
                required_capabilities=["generate_report", "trend_analysis"],
                exclude_ids=[self.agent_id],
            )
            if candidate is None:
                logger.warning("SearchAgent: AnalysisAgent registry'de bulunamadı, peer delegasyon atlandı")
                return None

            analysis_agent = candidate.agent
            logger.info(
                "SearchAgent → %s peer delegasyon: arama analizi (score=%.3f)",
                analysis_agent.name,
                candidate.similarity_score,
            )

            from uuid import UUID as _UUID
            raw_chain = context.get("_delegation_chain", [])
            chain: list[_UUID] = []
            for item in raw_chain:
                try:
                    chain.append(_UUID(item) if isinstance(item, str) else item)
                except (ValueError, AttributeError):
                    pass

            resp = await self._delegation_mgr.delegate(
                from_agent_id=self.agent_id,
                to_agent_id=analysis_agent.agent_id,
                to_agent_host=analysis_agent.host,
                to_agent_port=analysis_agent.port,
                task="Arama sonuçlarını analiz et ve rapor oluştur",
                context={
                    "search_results": search_data.get("search_results", []),
                    "summary": search_data.get("summary", ""),
                    "query": search_data.get("query", ""),
                    "original_task": context.get("original_task", task),
                    "title": f"Arama Analizi: {search_data.get('query', task)[:60]}",
                    "_delegation_chain": [str(i) for i in chain] + [str(self.agent_id)],
                },
                chain=chain,
                to_agent_base_path=analysis_agent.base_path,
            )

            return {
                "from_agent_id": str(self.agent_id),
                "from_agent_name": self.name,
                "to_agent_id": str(analysis_agent.agent_id),
                "to_agent_name": analysis_agent.name,
                "status": resp.status.value,
                "result": resp.result if resp.status == DelegationStatus.COMPLETED else None,
                "error": resp.error,
            }
        except Exception as exc:
            logger.warning("SearchAgent peer delegasyon hatası: %s", exc)
            return None


def _extract_query(task: str, original_task: str) -> str:
    """Görev açıklamasından arama sorgusunu çıkar."""
    import re as _re
    clean = _re.sub(
        r"\s*(hakkında\s+)?(web\s+)?(araştırma|araştır|bilgi topla|araştır|kaynak topla|özetle)\s*(yap|et|çıkar)?\s*\.?$",
        "",
        task.strip(),
        flags=_re.IGNORECASE,
    ).strip()

    for prefix in (
        "araştır ve özetle:", "araştır:", "hakkında bilgi topla:",
        "search for", "find information about", "look up",
    ):
        if clean.lower().startswith(prefix):
            clean = clean[len(prefix):].strip()
            break

    if len(clean) > 8:
        return clean[:200]
    if len(task) < 200:
        return task.strip()
    return original_task[:200].strip()


if __name__ == "__main__":
    import asyncio
    asyncio.run(SearchAgent().run())
