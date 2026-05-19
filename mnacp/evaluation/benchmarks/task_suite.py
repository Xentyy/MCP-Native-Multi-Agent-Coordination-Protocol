"""
Değerlendirme görev seti — senaryoları yükler ve çalıştırır.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from mnacp.evaluation.metrics import MetricsCollector, TaskResult

SCENARIOS_PATH = Path(__file__).parent / "scenarios.json"


def load_scenarios() -> list[dict[str, Any]]:
    with open(SCENARIOS_PATH, encoding="utf-8") as f:
        return json.load(f)


class BenchmarkRunner:
    def __init__(self, collector: MetricsCollector) -> None:
        self._collector = collector

    async def run_scenario(
        self,
        scenario: dict[str, Any],
        system_name: str,
        execute_fn,  # async (task: str) -> (success: bool, depth: int, count: int, correct: int, total: int)
    ) -> TaskResult:
        t0 = time.monotonic()
        deadlock = False
        try:
            success, depth, count, correct, total = await execute_fn(scenario["description"])
        except Exception as exc:
            success, depth, count, correct, total = False, 0, 0, 0, 0
            if "deadlock" in str(exc).lower() or "döngü" in str(exc).lower():
                deadlock = True

        latency_ms = (time.monotonic() - t0) * 1000

        result = TaskResult(
            task_id=str(uuid4()),
            scenario_id=scenario["id"],
            system=system_name,
            success=success,
            latency_ms=latency_ms,
            delegation_depth=depth,
            delegation_count=count,
            correct_agent_selections=correct,
            total_agent_selections=total,
            deadlock_detected=deadlock,
        )
        self._collector.record(result)
        return result

    async def run_all(
        self,
        system_name: str,
        execute_fn,
        repeat: int = 1,
    ) -> list[TaskResult]:
        scenarios = load_scenarios()
        results = []
        for scenario in scenarios:
            for _ in range(repeat):
                r = await self.run_scenario(scenario, system_name, execute_fn)
                results.append(r)
        return results
