"""
Entegrasyon testi — Registry + Agent kayıt + keşif + delegasyon akışı.
Sunucular conftest.py'deki live_servers fixture'ı tarafından yönetilir.
"""
from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

from tests.integration.conftest import (
    ANALYSIS_PORT,
    DATA_PORT,
    REGISTRY_URL,
)


@pytest.mark.asyncio
async def test_registry_health(live_servers):
    async with httpx.AsyncClient(timeout=5.0) as c:
        r = await c.get(f"{REGISTRY_URL}/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["agent_count"] == 4


@pytest.mark.asyncio
async def test_list_agents(live_servers):
    async with httpx.AsyncClient(timeout=5.0) as c:
        r = await c.get(f"{REGISTRY_URL}/agents")
    assert r.status_code == 200
    names = {a["name"] for a in r.json()}
    assert names == {"DataAgent", "SearchAgent", "AnalysisAgent", "CodeAgent"}


@pytest.mark.asyncio
async def test_discover_data_agent(live_servers):
    async with httpx.AsyncClient(timeout=5.0) as c:
        r = await c.post(f"{REGISTRY_URL}/discover", json={
            "task_description": "CSV dosyasını yükle ve istatistik hesapla",
            "top_k": 1,
        })
    assert r.status_code == 200
    assert r.json()[0]["agent"]["name"] == "DataAgent"


@pytest.mark.asyncio
async def test_discover_search_agent(live_servers):
    async with httpx.AsyncClient(timeout=5.0) as c:
        r = await c.post(f"{REGISTRY_URL}/discover", json={
            "task_description": "İnternette arama yap ve web sayfası getir",
            "top_k": 1,
        })
    assert r.status_code == 200
    assert r.json()[0]["agent"]["name"] == "SearchAgent"


@pytest.mark.asyncio
async def test_discover_analysis_agent(live_servers):
    async with httpx.AsyncClient(timeout=5.0) as c:
        r = await c.post(f"{REGISTRY_URL}/discover", json={
            "task_description": "Trend analizi yap ve rapor oluştur",
            "top_k": 1,
        })
    assert r.status_code == 200
    assert r.json()[0]["agent"]["name"] == "AnalysisAgent"


@pytest.mark.asyncio
async def test_data_agent_tool_call(live_servers):
    csv_content = "ad,yas\nAli,25\nVeli,30\nAyse,28"
    async with httpx.AsyncClient(timeout=5.0) as c:
        r = await c.post(
            f"http://127.0.0.1:{DATA_PORT}/tools/load_csv",
            json={"parameters": {"content": csv_content}},
        )
    assert r.status_code == 200
    result = r.json()["result"]
    assert len(result) == 3
    assert result[0]["ad"] == "Ali"


@pytest.mark.asyncio
async def test_data_agent_compute_statistics(live_servers):
    rows = [{"price": "10"}, {"price": "20"}, {"price": "30"}]
    async with httpx.AsyncClient(timeout=5.0) as c:
        r = await c.post(
            f"http://127.0.0.1:{DATA_PORT}/tools/compute_statistics",
            json={"parameters": {"rows": rows, "column": "price"}},
        )
    assert r.status_code == 200
    stats = r.json()["result"]
    assert stats["count"] == 3
    assert stats["mean"] == 20.0


@pytest.mark.asyncio
async def test_analysis_agent_trend(live_servers):
    async with httpx.AsyncClient(timeout=5.0) as c:
        r = await c.post(
            f"http://127.0.0.1:{ANALYSIS_PORT}/tools/trend_analysis",
            json={"parameters": {"values": [10, 20, 30, 40, 50]}},
        )
    assert r.status_code == 200
    assert r.json()["result"]["trend"] == "up"


@pytest.mark.asyncio
async def test_delegation_to_data_agent(live_servers):
    data_agent = live_servers["data_agent"]
    request = {
        "request": {
            "from_agent_id": str(uuid4()),
            "to_agent_id": str(data_agent.agent_id),
            "task": "CSV verilerinin istatistiklerini hesapla",
            "context": {
                "rows": [{"val": "5"}, {"val": "15"}, {"val": "25"}],
                "column": "val",
            },
            "delegation_chain": [],
            "max_depth": 5,
        }
    }
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(f"http://127.0.0.1:{DATA_PORT}/delegate", json=request)
    assert r.status_code == 200
    assert r.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_trust_recording(live_servers):
    async with httpx.AsyncClient(timeout=5.0) as c:
        agents = (await c.get(f"{REGISTRY_URL}/agents")).json()
        agent_id = agents[0]["agent_id"]
        r = await c.post(f"{REGISTRY_URL}/trust/record", json={
            "agent_id": agent_id,
            "event_type": "tool_call",
            "success": True,
            "latency_ms": 100.0,
        })
    assert r.status_code == 200
