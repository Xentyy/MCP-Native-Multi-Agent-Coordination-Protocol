"""
Araç önericisi — mevcut sistemdeki araçlara bakarak yeni rol için öneri üretir.
RoleBuilder'ı tamamlar: önce var olan araçları dene, yoksa yeni üret.
"""
from __future__ import annotations

from mnacp.agents.base_agent.registry_client import RegistryClient
from mnacp.protocol.schemas import ToolSchema


class ToolSuggester:
    def __init__(self, registry_url: str = "http://localhost:8000") -> None:
        self._registry_url = registry_url

    async def existing_tools(self) -> list[ToolSchema]:
        """Registry'deki tüm ajanlardan araç listesini topla."""
        try:
            async with RegistryClient(self._registry_url) as client:
                agents = await client.list_agents()
            tools = []
            seen = set()
            for agent in agents:
                for tool in agent.tools:
                    if tool.name not in seen:
                        tools.append(tool)
                        seen.add(tool.name)
            return tools
        except Exception:
            return []

    async def suggest_from_existing(self, description: str) -> list[ToolSchema]:
        """
        Var olan araçlar arasından açıklamaya uygun olanları öner.
        Kelime eşleşmesi ile basit skor hesaplar.
        """
        tools = await self.existing_tools()
        desc_words = set(description.lower().split())

        scored = []
        for tool in tools:
            tool_words = set((tool.name + " " + tool.description).lower().split())
            overlap = len(desc_words & tool_words)
            if overlap > 0:
                scored.append((overlap, tool))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [t for _, t in scored[:5]]
