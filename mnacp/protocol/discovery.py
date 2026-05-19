"""
Ajan keşif protokolü.

Orkestratör bir görevi çözecek ajan ararken bu modülü kullanır.
Registry'ye danışır, sonuçları filtreler ve en uygun adayı döndürür.
"""
from __future__ import annotations

import logging
from uuid import UUID

from mnacp.agents.base_agent.registry_client import RegistryClient
from mnacp.protocol.schemas import AgentInfo, DiscoveryRequest, DiscoveryResult

logger = logging.getLogger(__name__)


class DiscoveryProtocol:
    def __init__(self, registry_url: str = "http://localhost:8000") -> None:
        self._registry_url = registry_url

    async def find_best_agent(
        self,
        task: str,
        required_capabilities: list[str] | None = None,
        exclude_ids: list[UUID] | None = None,
        top_k: int = 3,
    ) -> DiscoveryResult | None:
        """Göreve en uygun tek ajanı döndür."""
        results = await self.find_agents(task, required_capabilities, exclude_ids, top_k)
        return results[0] if results else None

    async def find_agents(
        self,
        task: str,
        required_capabilities: list[str] | None = None,
        exclude_ids: list[UUID] | None = None,
        top_k: int = 3,
    ) -> list[DiscoveryResult]:
        """Göreve uygun ajanları sıralı olarak döndür."""
        request = DiscoveryRequest(
            task_description=task,
            required_capabilities=required_capabilities or [],
            top_k=top_k,
            exclude_agent_ids=exclude_ids or [],
        )
        async with RegistryClient(self._registry_url) as client:
            return await client.discover(request)

    async def resolve_tool_owner(
        self,
        tool_name: str,
        exclude_ids: list[UUID] | None = None,
    ) -> AgentInfo | None:
        """Belirli bir aracı sunan ajanı bul."""
        results = await self.find_agents(
            task=f"araç: {tool_name}",
            required_capabilities=[tool_name],
            exclude_ids=exclude_ids,
            top_k=5,
        )
        for r in results:
            if any(t.name == tool_name for t in r.agent.tools):
                return r.agent
        return None
