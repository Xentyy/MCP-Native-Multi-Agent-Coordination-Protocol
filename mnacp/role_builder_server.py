"""
No-Code Rol Oluşturucu HTTP sunucusu.

Frontend'in /roles sayfası bu API'ya bağlanır (localhost:8001).
Kullanıcının doğal dil açıklamasını alır, araç önerir ve onay sonrası
GenericAgent başlatarak registry'ye kaydeder.

Generic ajanlar bu sunucunun path'leri üzerinden hizmet verir:
  POST /agents/{agent_id}/tools/{tool_name}
  POST /agents/{agent_id}/delegate
"""
from __future__ import annotations

import asyncio
import logging
import os
from uuid import UUID

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

from mnacp.agents.base_agent.registry_client import RegistryClient  # noqa: E402
from mnacp.no_code.agents_store import load_agents, remove_agent, save_agent  # noqa: E402
from mnacp.no_code.generic_agent import GenericAgent  # noqa: E402
from mnacp.no_code.role_builder import RoleBuilder, RoleProposal, ToolSuggestion  # noqa: E402
from mnacp.no_code.validator import validate_proposal  # noqa: E402
from mnacp.protocol.schemas import AgentInfo, DelegationRequest  # noqa: E402

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

app = FastAPI(title="MNACP Role Builder", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

registry_url = os.environ.get("NEXT_PUBLIC_REGISTRY_URL", "http://localhost:8000")
role_builder_port = int(os.environ.get("ROLE_BUILDER_PORT", 8001))

# Role builder servis adı / host — registry'ye bu host ile duyurulur.
# Docker içinde container adı ("role-builder"), dışarıda "localhost".
role_builder_host = os.environ.get("ROLE_BUILDER_ADVERTISE_HOST", "localhost")

builder = RoleBuilder(registry_url=registry_url)

# Aktif generic ajanlar: agent_id (str) → GenericAgent
_generic_agents: dict[str, GenericAgent] = {}


@app.on_event("startup")
async def _restore_agents() -> None:
    """Sunucu başlarken kalıcı depodan generic ajanları geri yükle."""
    records = load_agents()
    for rec in records:
        try:
            from mnacp.no_code.role_builder import ToolSuggestion as _TS
            proposal = RoleProposal(
                agent_name=rec["agent_name"],
                agent_description=rec["agent_description"],
                tags=rec.get("tags", []),
                tools=[_TS(**t) for t in rec.get("tools", [])],
                rationale=rec.get("rationale", ""),
                user_description=rec.get("agent_description", ""),
            )
            from uuid import UUID as _UUID
            agent = GenericAgent(
                proposal=proposal,
                registry_host=role_builder_host,
                registry_port=role_builder_port,
                agent_id=_UUID(rec["agent_id"]),
            )
            registration = agent.to_registration()
            async with RegistryClient(registry_url) as client:
                await client.register(registration)
            _generic_agents[rec["agent_id"]] = agent
            logger.info("Geri yüklendi: %s (id=%s)", agent.name, agent.agent_id)
        except Exception as exc:
            logger.warning("Ajan geri yükleme başarısız (%s): %s", rec.get("agent_id"), exc)


# ─── DTO'lar ───────────────────────────────────────────────────────────────────

class SuggestRequest(BaseModel):
    description: str


class ToolProposalDTO(BaseModel):
    name: str
    description: str
    parameters: dict[str, str] = {}


class SuggestResponse(BaseModel):
    agent_name: str
    agent_description: str
    tags: list[str]
    tools: list[ToolProposalDTO]
    rationale: str


class CreateRequest(BaseModel):
    agent_name: str
    agent_description: str
    tags: list[str]
    tools: list[ToolProposalDTO]
    rationale: str = ""


# ─── Ana endpoint'ler ──────────────────────────────────────────────────────────

@app.post("/suggest", response_model=SuggestResponse)
async def suggest(body: SuggestRequest) -> SuggestResponse:
    """Doğal dil açıklamasından araç önerileri üret."""
    if not body.description.strip():
        raise HTTPException(status_code=400, detail="Açıklama boş olamaz")

    logger.info("Öneri istendi: %s", body.description[:80])
    proposal = await builder.suggest(body.description)

    return SuggestResponse(
        agent_name=proposal.agent_name,
        agent_description=proposal.agent_description,
        tags=proposal.tags,
        tools=[
            ToolProposalDTO(name=t.name, description=t.description, parameters=t.parameters)
            for t in proposal.tools
        ],
        rationale=proposal.rationale,
    )


@app.post("/create", response_model=AgentInfo)
async def create(body: CreateRequest) -> AgentInfo:
    """Onaylanan teklifi GenericAgent olarak başlat ve registry'ye kaydet."""
    logger.info("Ajan oluşturma istendi: %s", body.agent_name)

    proposal = RoleProposal(
        agent_name=body.agent_name,
        agent_description=body.agent_description,
        tags=body.tags,
        tools=[
            ToolSuggestion(name=t.name, description=t.description, parameters=t.parameters)
            for t in body.tools
        ],
        rationale=body.rationale,
        user_description=body.agent_description,
    )

    validation = validate_proposal(proposal)
    if not validation.valid:
        raise HTTPException(status_code=422, detail="; ".join(validation.errors))

    # GenericAgent oluştur — role-builder'ın kendi host:port'unu kullanır
    agent = GenericAgent(
        proposal=proposal,
        registry_host=role_builder_host,
        registry_port=role_builder_port,
    )

    # Registry'ye kaydet
    registration = agent.to_registration()
    async with RegistryClient(registry_url) as client:
        info = await client.register(registration)

    # Aktif ajanlar sözlüğüne ekle
    _generic_agents[str(agent.agent_id)] = agent
    save_agent({
        "agent_id": str(agent.agent_id),
        "agent_name": agent.name,
        "agent_description": agent.description,
        "tags": list(proposal.tags),
        "tools": [{"name": t.name, "description": t.description, "parameters": t.parameters} for t in proposal.tools],
        "rationale": proposal.rationale,
    })
    logger.info(
        "GenericAgent aktif: %s (id=%s) — /agents/%s/delegate",
        agent.name, agent.agent_id, agent.agent_id,
    )
    return info


# ─── Generic ajan proxy endpoint'leri ─────────────────────────────────────────

@app.post("/agents/{agent_id}/tools/{tool_name}")
async def generic_tool_call(agent_id: str, tool_name: str, request: Request):
    """Generic ajanın tool'unu çalıştır."""
    agent = _generic_agents.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Generic ajan bulunamadı: {agent_id}")

    try:
        body = await request.json()
    except Exception:
        body = {}
    parameters = body.get("parameters", body)

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, agent.execute_tool_sync, tool_name, parameters)
    return {"result": result}


@app.post("/agents/{agent_id}/delegate")
async def generic_delegate(agent_id: str, request: Request):
    """Generic ajana delegasyon gönder."""
    agent = _generic_agents.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Generic ajan bulunamadı: {agent_id}")

    body = await request.json()
    req_data = body.get("request", body)

    for key in ("from_agent_id", "to_agent_id"):
        if key in req_data and isinstance(req_data[key], str):
            req_data[key] = UUID(req_data[key])
    chain = req_data.get("delegation_chain", [])
    req_data["delegation_chain"] = [
        UUID(x) if isinstance(x, str) else x for x in chain
    ]
    delegation_req = DelegationRequest(**req_data)

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, agent.handle_delegation_sync, delegation_req)
    return result.model_dump(mode="json")


@app.get("/agents/{agent_id}/health")
async def generic_health(agent_id: str):
    agent = _generic_agents.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Ajan bulunamadı")
    return {"agent_id": agent_id, "name": agent.name, "status": "ok"}


@app.get("/agents")
async def list_generic_agents():
    """Aktif generic ajanları listele."""
    return [
        {"agent_id": aid, "name": a.name, "description": a.description}
        for aid, a in _generic_agents.items()
    ]


@app.delete("/agents/{agent_id}", status_code=204)
async def delete_generic_agent(agent_id: str):
    """Generic ajanı sil: bellekten kaldır, registry'den sil, kalıcı depodan çıkar."""
    if agent_id not in _generic_agents:
        raise HTTPException(status_code=404, detail="Ajan bulunamadı")
    _generic_agents.pop(agent_id)
    try:
        async with RegistryClient(registry_url) as client:
            await client.unregister(UUID(agent_id))
    except Exception as exc:
        logger.warning("Registry'den silme başarısız (%s): %s", agent_id, exc)
    remove_agent(agent_id)
    logger.info("Generic ajan silindi: %s", agent_id)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "role_builder", "generic_agents": len(_generic_agents)}


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("ROLE_BUILDER_PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
