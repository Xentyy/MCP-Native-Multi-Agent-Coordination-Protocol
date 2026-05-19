"""Agent Registry unit testleri."""
from __future__ import annotations

import pytest
from mnacp.protocol.schemas import (
    AgentRegistration,
    AgentStatus,
    DiscoveryRequest,
    ToolSchema,
    TrustEvent,
)
from mnacp.registry.agent_registry import AgentRegistry


@pytest.fixture
def registry():
    return AgentRegistry()


def _make_agent(name: str, description: str, tools: list[ToolSchema], port: int = 9000) -> AgentRegistration:
    return AgentRegistration(
        name=name,
        description=description,
        host="localhost",
        port=port,
        tools=tools,
        tags=[],
    )


@pytest.mark.asyncio
async def test_register_and_list(registry):
    agent = _make_agent(
        "DataAgent",
        "CSV veri işleme ve istatistik ajanı",
        [ToolSchema(name="load_csv", description="CSV dosyası yükler")],
    )
    info = await registry.register_agent(agent)
    assert info.name == "DataAgent"

    agents = await registry.list_agents()
    assert len(agents) == 1


@pytest.mark.asyncio
async def test_discover_returns_relevant_agent(registry):
    await registry.register_agent(_make_agent(
        "DataAgent",
        "CSV veri işleme ve istatistik",
        [ToolSchema(name="load_csv", description="CSV yükler"),
         ToolSchema(name="compute_statistics", description="İstatistik hesaplar")],
        port=9001,
    ))
    await registry.register_agent(_make_agent(
        "SearchAgent",
        "Web arama ve içerik özetleme",
        [ToolSchema(name="web_search", description="İnternette arama yapar"),
         ToolSchema(name="summarize", description="İçerik özetler")],
        port=9002,
    ))

    request = DiscoveryRequest(task_description="CSV dosyasından istatistik hesapla", top_k=1)
    results = await registry.discover(request)
    assert len(results) == 1
    assert results[0].agent.name == "DataAgent"


@pytest.mark.asyncio
async def test_discover_excludes_agent(registry):
    reg = _make_agent(
        "DataAgent", "CSV işleme",
        [ToolSchema(name="load_csv", description="CSV yükler")],
    )
    info = await registry.register_agent(reg)

    request = DiscoveryRequest(
        task_description="CSV işle",
        top_k=1,
        exclude_agent_ids=[info.agent_id],
    )
    results = await registry.discover(request)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_trust_score_decreases_on_failure(registry):
    agent = _make_agent(
        "Unreliable", "Güvenilmez ajan",
        [ToolSchema(name="flaky_tool", description="Bazen çöker")],
    )
    info = await registry.register_agent(agent)

    for _ in range(5):
        await registry.record_trust_event(TrustEvent(
            agent_id=info.agent_id,
            event_type="tool_call",
            success=False,
            latency_ms=5000,
        ))

    updated = await registry.get_agent(info.agent_id)
    assert updated.trust_score < 1.0


@pytest.mark.asyncio
async def test_unregister(registry):
    agent = _make_agent("Temp", "Geçici", [ToolSchema(name="t", description="d")])
    info = await registry.register_agent(agent)
    await registry.unregister_agent(info.agent_id)
    agents = await registry.list_agents()
    assert len(agents) == 0


@pytest.mark.asyncio
async def test_offline_agent_excluded_from_discovery(registry):
    agent = _make_agent(
        "Offline", "Çevrimdışı ajan",
        [ToolSchema(name="tool", description="bir araç")],
    )
    info = await registry.register_agent(agent)
    await registry.update_status(info.agent_id, AgentStatus.OFFLINE)

    request = DiscoveryRequest(task_description="bir araç kullan", top_k=3)
    results = await registry.discover(request)
    assert all(r.agent.name != "Offline" for r in results)
