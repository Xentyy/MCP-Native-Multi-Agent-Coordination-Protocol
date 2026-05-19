"""
Değerlendirme metrikleri — akademik karşılaştırma için.

Toplar:
- Görev tamamlama oranı
- Delegasyon doğruluğu
- Ortalama delegasyon derinliği
- P50/P90/P99 gecikme
- Deadlock tespit oranı
- No-code başarı oranı
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class TaskResult:
    task_id: str
    scenario_id: str
    system: str  # "mnacp" | "baseline_static" | "baseline_central"
    success: bool
    latency_ms: float
    delegation_depth: int
    delegation_count: int
    correct_agent_selections: int
    total_agent_selections: int
    deadlock_detected: bool
    timestamp: datetime = field(default_factory=datetime.utcnow)
    notes: str = ""


@dataclass
class EvaluationSummary:
    system: str
    scenario_id: str
    task_completion_rate: float
    delegation_accuracy: float
    avg_delegation_depth: float
    avg_delegation_count: float
    deadlock_rate: float
    p50_latency_ms: float
    p90_latency_ms: float
    p99_latency_ms: float
    total_runs: int


class MetricsCollector:
    def __init__(self) -> None:
        self._results: list[TaskResult] = []

    def record(self, result: TaskResult) -> None:
        self._results.append(result)

    def summarize(
        self,
        system: str | None = None,
        scenario_id: str | None = None,
    ) -> EvaluationSummary | None:
        results = self._results
        if system:
            results = [r for r in results if r.system == system]
        if scenario_id:
            results = [r for r in results if r.scenario_id == scenario_id]
        if not results:
            return None

        label_system = system or "all"
        label_scenario = scenario_id or "all"

        successes = sum(1 for r in results if r.success)
        task_completion_rate = successes / len(results)

        total_correct = sum(r.correct_agent_selections for r in results)
        total_selections = sum(r.total_agent_selections for r in results)
        delegation_accuracy = total_correct / total_selections if total_selections > 0 else 0.0

        depths = [r.delegation_depth for r in results]
        counts = [r.delegation_count for r in results]
        latencies = sorted(r.latency_ms for r in results)
        deadlocks = sum(1 for r in results if r.deadlock_detected)

        def percentile(data: list[float], p: float) -> float:
            if not data:
                return 0.0
            idx = int(len(data) * p / 100)
            idx = min(idx, len(data) - 1)
            return data[idx]

        return EvaluationSummary(
            system=label_system,
            scenario_id=label_scenario,
            task_completion_rate=round(task_completion_rate, 4),
            delegation_accuracy=round(delegation_accuracy, 4),
            avg_delegation_depth=round(statistics.mean(depths), 2),
            avg_delegation_count=round(statistics.mean(counts), 2),
            deadlock_rate=round(deadlocks / len(results), 4),
            p50_latency_ms=round(percentile(latencies, 50), 2),
            p90_latency_ms=round(percentile(latencies, 90), 2),
            p99_latency_ms=round(percentile(latencies, 99), 2),
            total_runs=len(results),
        )

    def all_systems(self) -> list[str]:
        return list({r.system for r in self._results})

    def all_scenarios(self) -> list[str]:
        return list({r.scenario_id for r in self._results})

    def compare(self, baseline_system: str, test_system: str) -> dict[str, Any]:
        """İki sistem arasındaki farkı hesapla."""
        baseline = self.summarize(system=baseline_system)
        test = self.summarize(system=test_system)
        if not baseline or not test:
            return {}

        def delta(a: float, b: float) -> dict[str, float]:
            diff = b - a
            pct = diff / (abs(a) + 1e-9) * 100
            return {"baseline": a, "test": b, "delta": round(diff, 4), "change_pct": round(pct, 2)}

        return {
            "task_completion_rate": delta(baseline.task_completion_rate, test.task_completion_rate),
            "delegation_accuracy": delta(baseline.delegation_accuracy, test.delegation_accuracy),
            "p90_latency_ms": delta(baseline.p90_latency_ms, test.p90_latency_ms),
            "avg_delegation_depth": delta(baseline.avg_delegation_depth, test.avg_delegation_depth),
            "deadlock_rate": delta(baseline.deadlock_rate, test.deadlock_rate),
        }

    def export(self) -> list[dict[str, Any]]:
        return [
            {
                "task_id": r.task_id,
                "scenario_id": r.scenario_id,
                "system": r.system,
                "success": r.success,
                "latency_ms": r.latency_ms,
                "delegation_depth": r.delegation_depth,
                "delegation_count": r.delegation_count,
                "delegation_accuracy": (
                    r.correct_agent_selections / r.total_agent_selections
                    if r.total_agent_selections > 0 else None
                ),
                "deadlock_detected": r.deadlock_detected,
                "timestamp": r.timestamp.isoformat(),
                "notes": r.notes,
            }
            for r in self._results
        ]


# Singleton
collector = MetricsCollector()
