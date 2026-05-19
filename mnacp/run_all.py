"""
Tüm servisleri tek komutla yerel olarak başlatan script.

Kullanım:
    cd mnacp
    python run_all.py

Bu script şunları başlatır:
1. Registry (port 8000)
2. DataAgent (port 9001)
3. SearchAgent (port 9002)
4. AnalysisAgent (port 9003)
5. Orchestrator (port 8002)
6. Role Builder (port 8001)

Frontend ayrı terminalde: cd frontend && npm run dev
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("MNACP")

REGISTRY_URL = "http://localhost:8000"


async def start_registry():
    """Registry HTTP sunucusunu başlat."""
    import uvicorn
    from mnacp.registry.server import app

    logger.info("📋 Registry başlatılıyor (port 8000)...")
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="warning")
    server = uvicorn.Server(config)
    await server.serve()


async def wait_for_registry(timeout: float = 15.0):
    """Registry'nin hazır olmasını bekle."""
    import httpx

    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            async with httpx.AsyncClient() as c:
                r = await c.get(f"{REGISTRY_URL}/health", timeout=2.0)
                if r.status_code == 200:
                    logger.info("✅ Registry hazır")
                    return True
        except Exception:
            pass
        await asyncio.sleep(0.5)
    logger.error("❌ Registry başlatılamadı")
    return False


async def start_agent(agent_cls, name: str, port: int):
    """Bir ajanı registry'ye kaydet ve HTTP sunucusunu başlat."""
    import uvicorn

    agent = agent_cls(host="localhost", port=port, registry_url=REGISTRY_URL)
    await agent.start()
    logger.info("🤖 %s başlatıldı (port %d)", name, port)

    app = agent.build_http_app()
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="warning")
    server = uvicorn.Server(config)
    await server.serve()


async def start_orchestrator():
    """Orkestratör HTTP sunucusunu başlat."""
    import uvicorn
    from mnacp.orchestrator_server import app

    logger.info("🧠 Orkestratör başlatılıyor (port 8002)...")
    config = uvicorn.Config(app, host="0.0.0.0", port=8002, log_level="warning")
    server = uvicorn.Server(config)
    await server.serve()


async def start_role_builder():
    """Role Builder HTTP sunucusunu başlat."""
    import uvicorn
    from mnacp.role_builder_server import app

    logger.info("🛠️  Role Builder başlatılıyor (port 8001)...")
    config = uvicorn.Config(app, host="0.0.0.0", port=8001, log_level="warning")
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    from mnacp.agents.example_agents.analysis_agent.agent import AnalysisAgent
    from mnacp.agents.example_agents.data_agent.agent import DataAgent
    from mnacp.agents.example_agents.search_agent.agent import SearchAgent

    logger.info("=" * 60)
    logger.info("MNACP — Multi-Agent Coordination Protocol")
    logger.info("=" * 60)

    # 1. Registry'yi başlat
    registry_task = asyncio.create_task(start_registry())
    await asyncio.sleep(1)

    if not await wait_for_registry():
        sys.exit(1)

    # 2. Ajanları başlat
    agent_tasks = [
        asyncio.create_task(start_agent(DataAgent, "DataAgent", 9001)),
        asyncio.create_task(start_agent(SearchAgent, "SearchAgent", 9002)),
        asyncio.create_task(start_agent(AnalysisAgent, "AnalysisAgent", 9003)),
    ]
    await asyncio.sleep(2)

    # 3. Orkestratör ve Role Builder
    orch_task = asyncio.create_task(start_orchestrator())
    rb_task = asyncio.create_task(start_role_builder())

    logger.info("")
    logger.info("=" * 60)
    logger.info("✅ Tüm servisler hazır!")
    logger.info("")
    logger.info("  📋 Registry       → http://localhost:8000")
    logger.info("  🤖 DataAgent      → http://localhost:9001")
    logger.info("  🔍 SearchAgent    → http://localhost:9002")
    logger.info("  📊 AnalysisAgent  → http://localhost:9003")
    logger.info("  🧠 Orchestrator   → http://localhost:8002")
    logger.info("  🛠️  Role Builder   → http://localhost:8001")
    logger.info("")
    logger.info("  🌐 Frontend için ayrı terminalde:")
    logger.info("     cd frontend && npm run dev")
    logger.info("     → http://localhost:3000")
    logger.info("=" * 60)

    # Tüm görevlerin bitmesini bekle (Ctrl+C ile durur)
    await asyncio.gather(
        registry_task, *agent_tasks, orch_task, rb_task,
        return_exceptions=True,
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n🛑 MNACP kapatılıyor...")
