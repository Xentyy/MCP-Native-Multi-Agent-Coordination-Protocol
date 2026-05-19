"""
Evaluation runner'lar — bir senaryo metnini sisteme verip
(success, depth, count, correct, total) tuple'ı döndürür.

execute_mnacp: gerçek orkestratör HTTP'sine SSE stream'i okur,
delegasyon zincirini gözlemler, doğru ajan seçimini sayar.
"""
from __future__ import annotations

import json
import os

import httpx

# Senaryolarda required_agents alanı var. Bunu test sırasında
# orkestratörün gerçekte hangi ajanları kullandığıyla kıyaslayacağız.

ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8002")
DEFAULT_TIMEOUT = 90.0


async def execute_mnacp(
    task: str,
    expected_agents: list[str] | None = None,
) -> tuple[bool, int, int, int, int]:
    """
    Orkestratöre /run/stream üzerinden görev gönder, SSE event'lerini topla.
    Döndürür: (success, depth, delegation_count, correct_selections, total_selections)
    """
    expected = set(expected_agents or [])
    delegation_count = 0
    max_depth = 0
    seen_agents: set[str] = set()
    success = False
    has_final_answer = False

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            async with client.stream(
                "POST",
                f"{ORCHESTRATOR_URL}/run/stream",
                json={"task": task},
            ) as response:
                response.raise_for_status()
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    while "\n\n" in buffer:
                        block, buffer = buffer.split("\n\n", 1)
                        for line in block.split("\n"):
                            if not line.startswith("data:"):
                                continue
                            payload = line[5:].strip()
                            if not payload:
                                continue
                            try:
                                event = json.loads(payload)
                            except json.JSONDecodeError:
                                continue
                            etype = event.get("type")

                            if etype == "subtask_start":
                                name = event.get("agent_name")
                                if name:
                                    seen_agents.add(name)
                                    delegation_count += 1
                                    max_depth = max(max_depth, 1)
                            elif etype == "peer_delegation":
                                # ajan→ajan delegasyon zinciri 2. seviye
                                from_n = event.get("from_agent_name")
                                to_n = event.get("to_agent_name")
                                if from_n:
                                    seen_agents.add(from_n)
                                if to_n:
                                    seen_agents.add(to_n)
                                delegation_count += 1
                                max_depth = max(max_depth, 2)
                            elif etype == "final_answer":
                                has_final_answer = True
                                success = True
                            elif etype == "error":
                                success = False
    except Exception:
        return False, 0, 0, 0, len(expected)

    if not has_final_answer:
        success = False

    # Doğruluk: beklenen ajanlardan kaç tanesi gerçekten kullanıldı?
    if expected:
        correct = len(seen_agents & expected)
        total = len(expected)
    else:
        correct = len(seen_agents)
        total = max(1, len(seen_agents))

    return success, max_depth, delegation_count, correct, total


def make_mnacp_runner(scenario: dict):
    """Scenario'nun expected_agents'ını closure'da yakala."""
    expected = scenario.get("required_agents", [])

    async def runner(task: str):
        return await execute_mnacp(task, expected_agents=expected)

    return runner


def make_static_runner(scenario: dict):
    """Statik baseline runner — beklenen ajan listesine göre doğruluk hesaplar."""
    from mnacp.evaluation.baseline.static_assignment import route_task

    expected = scenario.get("required_agents", [])

    async def runner(task: str):
        chosen = route_task(task)
        # Statik tek ajan seçer — beklenen listede varsa doğru
        correct = 1 if chosen in expected else 0
        total = max(1, len(expected))
        # success: en az 1 doğru ajan seçildiyse
        success = correct > 0
        return success, 0, 1, correct, total

    return runner


def make_central_runner(scenario: dict):
    """Merkezi baseline runner — tüm araçlar tek ajanda."""
    from mnacp.evaluation.baseline.no_delegation import execute_central

    async def runner(task: str):
        return await execute_central(task)

    return runner
