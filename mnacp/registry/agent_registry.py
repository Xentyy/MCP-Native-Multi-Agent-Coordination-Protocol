from __future__ import annotations

import asyncio
import logging
from uuid import UUID

import numpy as np
from mnacp.protocol.schemas import (
    AgentInfo,
    AgentRegistration,
    AgentStatus,
    DiscoveryRequest,
    DiscoveryResult,
    TrustEvent,
)
from mnacp.registry.capability_embedder import CapabilityEmbedder
from mnacp.registry.tool_index import ToolIndex
from mnacp.registry.trust_scorer import TrustScorer

logger = logging.getLogger(__name__)


class AgentRegistry:
    """
    Merkezi ajan kayıt ve keşif servisi.

    Tüm ajanlar başlarken buraya register_agent() ile kaydolur.
    Orkestratör, discover() ile göreve uygun ajanı bulur.
    """

    def __init__(self) -> None:
        self._agents: dict[str, AgentRegistration] = {}
        self._embedder = CapabilityEmbedder()
        self._tool_index = ToolIndex()
        self._trust_scorer = TrustScorer()
        self._embeddings: dict[str, np.ndarray] = {}
        self._lock = asyncio.Lock()
        self._fitted = False

    # ------------------------------------------------------------------
    # Kayıt işlemleri
    # ------------------------------------------------------------------

    async def register_agent(self, registration: AgentRegistration) -> AgentInfo:
        async with self._lock:
            # Aynı host:port'ta eski kayıt varsa temizle (container yeniden başlatma)
            stale = [
                old_id for old_id, old_reg in self._agents.items()
                if old_reg.host == registration.host
                and old_reg.port == registration.port
                and old_id != str(registration.agent_id)
            ]
            for old_id in stale:
                self._tool_index.unregister(self._agents[old_id].agent_id)
                self._embeddings.pop(old_id, None)
                del self._agents[old_id]
                logger.info("Stale registration removed: %s", old_id)

            aid = str(registration.agent_id)
            self._agents[aid] = registration
            self._tool_index.register(registration.agent_id, registration.tools)
            await self._refit_embeddings()
            logger.info("Agent registered: %s (%s)", registration.name, aid)
            return self._to_info(registration)

    async def unregister_agent(self, agent_id: UUID) -> None:
        async with self._lock:
            aid = str(agent_id)
            if aid not in self._agents:
                return
            del self._agents[aid]
            self._tool_index.unregister(agent_id)
            self._embeddings.pop(aid, None)
            await self._refit_embeddings()
            logger.info("Agent unregistered: %s", aid)

    async def update_status(self, agent_id: UUID, status: AgentStatus) -> None:
        async with self._lock:
            aid = str(agent_id)
            if aid in self._agents:
                self._agents[aid].status = status

    # ------------------------------------------------------------------
    # Keşif
    # ------------------------------------------------------------------

    async def discover(self, request: DiscoveryRequest) -> list[DiscoveryResult]:
        async with self._lock:
            if not self._agents:
                return []

            if not self._fitted:
                await self._refit_embeddings()

            query_vec = self._embedder.embed_query(request.task_description)
            exclude = [str(i) for i in request.exclude_agent_ids]

            online_vecs = {
                aid: vec
                for aid, vec in self._embeddings.items()
                if self._agents[aid].status == AgentStatus.ONLINE and aid not in exclude
            }

            if not online_vecs:
                return []

            top = self._embedder.top_k_agents(query_vec, online_vecs, k=request.top_k)

            results = []
            for aid, sim in top:
                agent = self._agents[aid]
                trust = self._trust_scorer.score(agent.agent_id)
                final_score = 0.7 * sim + 0.3 * trust

                matched = [
                    t.name
                    for t in agent.tools
                    if any(
                        cap.lower() in t.name.lower() or cap.lower() in t.description.lower()
                        for cap in request.required_capabilities
                    )
                ] if request.required_capabilities else [t.name for t in agent.tools]

                results.append(
                    DiscoveryResult(
                        agent=self._to_info(agent),
                        similarity_score=final_score,
                        matched_tools=matched,
                    )
                )

            results.sort(key=lambda r: r.similarity_score, reverse=True)
            return results

    # ------------------------------------------------------------------
    # Güven skoru
    # ------------------------------------------------------------------

    async def record_trust_event(self, event: TrustEvent) -> None:
        async with self._lock:
            score = self._trust_scorer.record(event)
            aid = str(event.agent_id)
            if aid in self._agents:
                self._agents[aid].trust_score = score

    # ------------------------------------------------------------------
    # Sorgulama yardımcıları
    # ------------------------------------------------------------------

    async def get_agent(self, agent_id: UUID) -> AgentInfo | None:
        async with self._lock:
            agent = self._agents.get(str(agent_id))
            return self._to_info(agent) if agent else None

    async def list_agents(self) -> list[AgentInfo]:
        async with self._lock:
            return [self._to_info(a) for a in self._agents.values()]

    async def get_agent_trends(self) -> dict[str, str]:
        """Her kayıtlı ajan için güven skoru trendini döndür."""
        async with self._lock:
            return {
                aid: self._trust_scorer.get_trend(agent.agent_id)
                for aid, agent in self._agents.items()
            }

    async def reset(self) -> None:
        async with self._lock:
            self._agents.clear()
            self._embeddings.clear()
            self._fitted = False
            logger.info("Registry reset.")

    # ------------------------------------------------------------------
    # İç yardımcılar
    # ------------------------------------------------------------------

    async def _refit_embeddings(self) -> None:
        if not self._agents:
            self._fitted = False
            return
        agents = list(self._agents.values())
        from mnacp.registry.capability_embedder import _text_for_agent
        texts = [_text_for_agent(a) for a in agents]
        self._embedder.fit(texts)
        for agent in agents:
            self._embeddings[str(agent.agent_id)] = self._embedder.embed_agent(agent)
        self._fitted = True

    @staticmethod
    def _to_info(agent: AgentRegistration) -> AgentInfo:
        return AgentInfo(
            agent_id=agent.agent_id,
            name=agent.name,
            description=agent.description,
            host=agent.host,
            port=agent.port,
            tools=agent.tools,
            status=agent.status,
            trust_score=agent.trust_score,
            tags=agent.tags,
            base_path=agent.base_path,
        )


# Singleton — tüm modüller bu nesneyi import eder
registry = AgentRegistry()
