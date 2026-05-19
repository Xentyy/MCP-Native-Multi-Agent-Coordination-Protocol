"""
Docker agent entrypoint — AGENT_TYPE ortam değişkenine göre uygun ajanı başlatır.
"""
import asyncio
import logging
import os
import sys

AGENT_TYPE = os.environ.get("AGENT_TYPE", "data")
AGENT_PORT = int(os.environ.get("AGENT_PORT", "9000"))
REGISTRY_URL = os.environ.get("REGISTRY_URL", "http://localhost:8000")
# Registry'de duyurulacak host. Docker'da servis adı, dışarıdan localhost.
ADVERTISE_HOST = os.environ.get("ADVERTISE_HOST", f"{AGENT_TYPE}-agent")

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def main():
    common = dict(
        host="0.0.0.0",
        port=AGENT_PORT,
        registry_url=REGISTRY_URL,
        advertise_host=ADVERTISE_HOST,
    )
    if AGENT_TYPE == "data":
        from mnacp.agents.example_agents.data_agent.agent import DataAgent
        agent = DataAgent(**common)
    elif AGENT_TYPE == "search":
        from mnacp.agents.example_agents.search_agent.agent import SearchAgent
        agent = SearchAgent(**common)
    elif AGENT_TYPE == "analysis":
        from mnacp.agents.example_agents.analysis_agent.agent import AnalysisAgent
        agent = AnalysisAgent(**common)
    elif AGENT_TYPE == "code":
        from mnacp.agents.example_agents.code_agent.agent import CodeAgent
        agent = CodeAgent(**common)
    else:
        print(f"Bilinmeyen AGENT_TYPE: {AGENT_TYPE}", file=sys.stderr)
        sys.exit(1)

    print(
        f"Başlatılıyor: {AGENT_TYPE} (port={AGENT_PORT}, "
        f"advertise={ADVERTISE_HOST}, registry={REGISTRY_URL})"
    )
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
