"""
Entegrasyon testleri için session-scope sunucu fixture'ları.
Sunucular ayrı thread'lerde çalıştırılır — async fixture karmaşıklığından kaçınır.
"""
from __future__ import annotations

import asyncio
import threading
import time

import httpx
import pytest
import uvicorn
from mnacp.agents.example_agents.analysis_agent.agent import AnalysisAgent
from mnacp.agents.example_agents.code_agent.agent import CodeAgent
from mnacp.agents.example_agents.data_agent.agent import DataAgent
from mnacp.agents.example_agents.search_agent.agent import SearchAgent
from mnacp.registry.server import app as registry_app

REGISTRY_PORT = 18000
DATA_PORT     = 19001
SEARCH_PORT   = 19002
ANALYSIS_PORT = 19003
CODE_PORT     = 19004
REGISTRY_URL  = f"http://127.0.0.1:{REGISTRY_PORT}"


def _wait_http_sync(url: str, retries: int = 50, delay: float = 0.3) -> bool:
    for _ in range(retries):
        try:
            r = httpx.get(url, timeout=1.0)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(delay)
    return False


def _run_server_in_thread(app, port: int) -> uvicorn.Server:
    """Uvicorn sunucusunu arka plan thread'inde başlat, Server nesnesini döndür."""
    cfg = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(cfg)

    def _target():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(server.serve())

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    return server


@pytest.fixture(scope="session")
def live_servers():
    """Registry ve 3 ajanı session boyunca thread'lerde ayakta tut."""
    servers: list[uvicorn.Server] = []

    # --- Registry ---
    srv = _run_server_in_thread(registry_app, REGISTRY_PORT)
    servers.append(srv)
    assert _wait_http_sync(f"{REGISTRY_URL}/health"), "Registry başlamadı"

    # --- Ajanları kaydet (sync httpx ile registry'e POST) ---
    loop = asyncio.new_event_loop()

    data_agent     = DataAgent(host="127.0.0.1", port=DATA_PORT,     registry_url=REGISTRY_URL)
    search_agent   = SearchAgent(host="127.0.0.1", port=SEARCH_PORT, registry_url=REGISTRY_URL)
    analysis_agent = AnalysisAgent(host="127.0.0.1", port=ANALYSIS_PORT, registry_url=REGISTRY_URL)
    code_agent     = CodeAgent(host="127.0.0.1", port=CODE_PORT,     registry_url=REGISTRY_URL)

    loop.run_until_complete(data_agent.start())
    loop.run_until_complete(search_agent.start())
    loop.run_until_complete(analysis_agent.start())
    loop.run_until_complete(code_agent.start())

    # --- Ajan HTTP sunucularını başlat ---
    srv = _run_server_in_thread(data_agent.build_http_app(), DATA_PORT)
    servers.append(srv)
    assert _wait_http_sync(f"http://127.0.0.1:{DATA_PORT}/health"), "DataAgent başlamadı"

    srv = _run_server_in_thread(search_agent.build_http_app(), SEARCH_PORT)
    servers.append(srv)
    assert _wait_http_sync(f"http://127.0.0.1:{SEARCH_PORT}/health"), "SearchAgent başlamadı"

    srv = _run_server_in_thread(analysis_agent.build_http_app(), ANALYSIS_PORT)
    servers.append(srv)
    assert _wait_http_sync(f"http://127.0.0.1:{ANALYSIS_PORT}/health"), "AnalysisAgent başlamadı"

    srv = _run_server_in_thread(code_agent.build_http_app(), CODE_PORT)
    servers.append(srv)
    assert _wait_http_sync(f"http://127.0.0.1:{CODE_PORT}/health"), "CodeAgent başlamadı"

    yield {
        "data_agent": data_agent,
        "search_agent": search_agent,
        "analysis_agent": analysis_agent,
        "code_agent": code_agent,
        "registry_url": REGISTRY_URL,
        "data_port": DATA_PORT,
        "search_port": SEARCH_PORT,
        "analysis_port": ANALYSIS_PORT,
        "code_port": CODE_PORT,
    }

    for s in servers:
        s.should_exit = True
    time.sleep(0.5)
    loop.close()
