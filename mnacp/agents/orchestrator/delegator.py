"""
Delegasyon karar motoru — hangi alt görevi hangi ajana vereceğine karar verir.
Registry'den aday ajanları bulur, güven skoruna göre sıralar ve seçer.
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from mnacp.agents.orchestrator.decomposer import SubTask
from mnacp.protocol.delegation import DelegationManager
from mnacp.protocol.discovery import DiscoveryProtocol
from mnacp.protocol.schemas import AgentInfo, DelegationResponse, DelegationStatus, DiscoveryResult

logger = logging.getLogger(__name__)


class DelegationDecision:
    def __init__(self, subtask: SubTask, agent: AgentInfo, score: float) -> None:
        self.subtask = subtask
        self.agent = agent
        self.score = score


class Delegator:
    def __init__(
        self,
        orchestrator_id: UUID,
        registry_url: str = "http://localhost:8000",
        max_depth: int = 5,
    ) -> None:
        self._orchestrator_id = orchestrator_id
        self._discovery = DiscoveryProtocol(registry_url)
        self._delegation = DelegationManager(max_depth=max_depth)

    async def find_agent_for(
        self,
        subtask: SubTask,
        exclude_ids: list[UUID] | None = None,
    ) -> DiscoveryResult | None:
        return await self._discovery.find_best_agent(
            task=subtask.description,
            required_capabilities=subtask.required_capabilities,
            exclude_ids=exclude_ids,
        )

    @staticmethod
    def _agent_has_tool(agent: AgentInfo, capabilities: list[str]) -> bool:
        """Ajan, gerekli capability'lerden EN AZ BİRİNİ tool adı olarak sunuyor mu?

        Açıklama içinde geçmesi yetmez — sıkı eşleşme gerek (yoksa AnalysisAgent
        'compute_statistics'i 'açıklamada statistics geçiyor' diye kapıyor).
        """
        if not capabilities:
            return True  # capability yoksa similarity yeter
        tool_names = {t.name.lower() for t in agent.tools}
        for cap in capabilities:
            cap_l = cap.lower()
            if cap_l in tool_names:
                return True
            # substring: 'load_csv' isteği 'load_csv_v2' tool'unu eşleştirir
            if any(cap_l in tn or tn in cap_l for tn in tool_names):
                return True
        return False

    async def pick_candidate(
        self,
        subtask: SubTask,
        exclude_ids: list[UUID] | None = None,
    ) -> DiscoveryResult | None:
        """Top-3 adayı çek; tool kapasitesi gerçekten olanı tercih et."""
        results = await self._discovery.find_agents(
            task=subtask.description,
            required_capabilities=subtask.required_capabilities,
            exclude_ids=exclude_ids,
            top_k=3,
        )
        if not results:
            return None

        for r in results:
            if self._agent_has_tool(r.agent, subtask.required_capabilities):
                return r
        # Hiçbir aday gerçek araca sahip değil — en yüksek similarity'li ilkini dön
        return results[0]

    async def execute_subtask(
        self,
        subtask: SubTask,
        context: dict[str, Any],
        chain: list[UUID],
        exclude_ids: list[UUID] | None = None,
    ) -> DelegationResponse:
        candidate = await self.pick_candidate(subtask, exclude_ids)

        if candidate is None:
            return DelegationResponse(
                request_id=__import__("uuid").uuid4(),
                status=DelegationStatus.FAILED,
                error=f"Uygun ajan bulunamadı: '{subtask.description[:60]}'",
            )

        agent = candidate.agent
        subtask.assigned_agent_id = str(agent.agent_id)
        has_real_tool = self._agent_has_tool(agent, subtask.required_capabilities)
        logger.info(
            "Delegasyon: subtask=%s → agent=%s (score=%.3f, has_tool=%s)",
            subtask.id, agent.name, candidate.similarity_score, has_real_tool,
        )

        return await self._delegation.delegate(
            from_agent_id=self._orchestrator_id,
            to_agent_id=agent.agent_id,
            to_agent_host=agent.host,
            to_agent_port=agent.port,
            task=subtask.description,
            context=context,
            chain=chain,
            to_agent_base_path=agent.base_path,
        )

    def get_stats(self) -> dict[str, Any]:
        return self._delegation.get_stats()

    def get_delegation_history(self) -> list[dict[str, Any]]:
        return self._delegation.get_history()
