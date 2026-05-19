"""Registry HTTP istemcisi — her ajan bu sınıf üzerinden registry'ye erişir."""
from __future__ import annotations

import logging
from uuid import UUID

import httpx
from mnacp.protocol.schemas import (
    AgentInfo,
    AgentRegistration,
    AgentStatus,
    DiscoveryRequest,
    DiscoveryResult,
    TrustEvent,
)

logger = logging.getLogger(__name__)


class RegistryClient:
    def __init__(self, registry_url: str = "http://localhost:8000") -> None:
        self._url = registry_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "RegistryClient":
        self._client = httpx.AsyncClient(timeout=10.0)
        return self

    async def __aexit__(self, *_) -> None:
        if self._client:
            await self._client.aclose()

    def _c(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("RegistryClient bir async context manager içinde kullanılmalı")
        return self._client

    async def register(self, registration: AgentRegistration) -> AgentInfo:
        r = await self._c().post(
            f"{self._url}/agents/register",
            content=registration.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )
        r.raise_for_status()
        return AgentInfo.model_validate(r.json())

    async def unregister(self, agent_id: UUID) -> None:
        r = await self._c().delete(f"{self._url}/agents/{agent_id}")
        r.raise_for_status()

    async def update_status(self, agent_id: UUID, status: AgentStatus) -> None:
        r = await self._c().patch(
            f"{self._url}/agents/{agent_id}/status",
            params={"status": status.value},
        )
        r.raise_for_status()

    async def discover(self, request: DiscoveryRequest) -> list[DiscoveryResult]:
        r = await self._c().post(
            f"{self._url}/discover",
            content=request.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )
        r.raise_for_status()
        return [DiscoveryResult.model_validate(x) for x in r.json()]

    async def record_trust(self, event: TrustEvent) -> None:
        r = await self._c().post(
            f"{self._url}/trust/record",
            content=event.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )
        r.raise_for_status()

    async def get_agent(self, agent_id: UUID) -> AgentInfo | None:
        r = await self._c().get(f"{self._url}/agents/{agent_id}")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return AgentInfo.model_validate(r.json())

    async def list_agents(self) -> list[AgentInfo]:
        r = await self._c().get(f"{self._url}/agents")
        r.raise_for_status()
        return [AgentInfo.model_validate(x) for x in r.json()]

    async def health(self) -> bool:
        try:
            r = await self._c().get(f"{self._url}/health", timeout=3.0)
            return r.status_code == 200
        except Exception:
            return False
