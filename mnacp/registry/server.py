"""Registry HTTP sunucusu — ajanlar bu API'ya kaydolur ve keşif yapar."""
from __future__ import annotations

import os
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mnacp.protocol.schemas import (
    AgentInfo,
    AgentRegistration,
    AgentStatus,
    DiscoveryRequest,
    DiscoveryResult,
    TrustEvent,
)
from mnacp.registry.agent_registry import registry

app = FastAPI(title="MNACP Agent Registry", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


_REGISTRY_API_KEY = os.environ.get("REGISTRY_API_KEY", "")


@app.post("/agents/register", response_model=AgentInfo)
async def register_agent(body: AgentRegistration) -> AgentInfo:
    if _REGISTRY_API_KEY and body.api_key != _REGISTRY_API_KEY:
        raise HTTPException(status_code=403, detail="Geçersiz registry API key")
    return await registry.register_agent(body)


@app.delete("/agents/{agent_id}")
async def unregister_agent(agent_id: UUID) -> dict:
    await registry.unregister_agent(agent_id)
    return {"status": "ok"}


@app.patch("/agents/{agent_id}/status")
async def update_status(agent_id: UUID, status: AgentStatus) -> dict:
    await registry.update_status(agent_id, status)
    return {"status": "ok"}


@app.get("/agents", response_model=list[AgentInfo])
async def list_agents() -> list[AgentInfo]:
    return await registry.list_agents()


@app.get("/agents/{agent_id}", response_model=AgentInfo)
async def get_agent(agent_id: UUID) -> AgentInfo:
    info = await registry.get_agent(agent_id)
    if not info:
        raise HTTPException(status_code=404, detail="Agent not found")
    return info


@app.post("/discover", response_model=list[DiscoveryResult])
async def discover(body: DiscoveryRequest) -> list[DiscoveryResult]:
    return await registry.discover(body)


@app.post("/trust/record")
async def record_trust(event: TrustEvent) -> dict:
    await registry.record_trust_event(event)
    return {"status": "ok"}


@app.get("/agents/trends")
async def get_agent_trends() -> dict[str, str]:
    """Her ajan için güven skoru trendini döndür: 'improving' | 'degrading' | 'stable'."""
    return await registry.get_agent_trends()


@app.post("/reset")
async def reset_registry() -> dict:
    await registry.reset()
    return {"status": "ok"}


@app.get("/health")
async def health() -> dict:
    agents = await registry.list_agents()
    return {"status": "ok", "agent_count": len(agents)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
