"""Metrik sistemi ve baseline değerlendirme testleri."""
from __future__ import annotations

import pytest
from mnacp.evaluation.baseline.no_delegation import execute_central
from mnacp.evaluation.baseline.static_assignment import execute_static, route_task
from mnacp.evaluation.benchmarks.task_suite import BenchmarkRunner, load_scenarios
from mnacp.evaluation.metrics import MetricsCollector, TaskResult

# ------------------------------------------------------------------
# MetricsCollector testleri
# ------------------------------------------------------------------

def make_result(system: str, scenario: str, success: bool, latency: float,
                depth: int = 1, count: int = 1, correct: int = 1, total: int = 1) -> TaskResult:
    return TaskResult(
        task_id=f"{system}-{scenario}",
        scenario_id=scenario,
        system=system,
        success=success,
        latency_ms=latency,
        delegation_depth=depth,
        delegation_count=count,
        correct_agent_selections=correct,
        total_agent_selections=total,
        deadlock_detected=False,
    )


def test_task_completion_rate():
    collector = MetricsCollector()
    for i in range(8):
        collector.record(make_result("mnacp", "S1", success=(i < 8), latency=100.0))
    for _ in range(2):
        collector.record(make_result("mnacp", "S1", success=False, latency=200.0))
    summary = collector.summarize(system="mnacp")
    assert summary.task_completion_rate == 0.8
    assert summary.total_runs == 10


def test_latency_percentiles():
    collector = MetricsCollector()
    latencies = [float(i * 100) for i in range(1, 11)]  # 100..1000
    for lat in latencies:
        collector.record(make_result("mnacp", "S1", success=True, latency=lat))
    summary = collector.summarize(system="mnacp")
    # p50: idx = int(10*50/100) = 5 → sorted[5] = 600.0
    assert summary.p50_latency_ms == 600.0
    # p90: idx = int(10*90/100) = 9 → sorted[9] = 1000.0
    assert summary.p90_latency_ms == 1000.0


def test_delegation_accuracy():
    collector = MetricsCollector()
    collector.record(make_result("mnacp", "S1", True, 100, correct=3, total=3))
    collector.record(make_result("mnacp", "S1", True, 100, correct=2, total=3))
    summary = collector.summarize(system="mnacp")
    assert abs(summary.delegation_accuracy - (5/6)) < 0.001


def test_compare_two_systems():
    collector = MetricsCollector()
    for _ in range(5):
        collector.record(make_result("baseline", "S1", True, 500))
        collector.record(make_result("mnacp", "S1", True, 200))
    comparison = collector.compare("baseline", "mnacp")
    assert "p90_latency_ms" in comparison
    assert comparison["p90_latency_ms"]["delta"] < 0  # mnacp daha hızlı


def test_export_format():
    collector = MetricsCollector()
    collector.record(make_result("mnacp", "S1", True, 150))
    exported = collector.export()
    assert len(exported) == 1
    assert "task_id" in exported[0]
    assert "system" in exported[0]
    assert exported[0]["system"] == "mnacp"


# ------------------------------------------------------------------
# Baseline testleri
# ------------------------------------------------------------------

def test_static_routing_csv():
    assert route_task("CSV dosyasını yükle") == "DataAgent"


def test_static_routing_search():
    assert route_task("web'de ara") == "SearchAgent"


def test_static_routing_analysis():
    assert route_task("trend analizi yap") == "AnalysisAgent"


@pytest.mark.asyncio
async def test_static_execute():
    result = await execute_static("istatistik hesapla")
    success, depth, count, correct, total = result
    assert success
    assert depth == 0  # delegasyon yok


@pytest.mark.asyncio
async def test_central_execute():
    result = await execute_central("CSV yükle ve istatistik hesapla ve rapor üret")
    success, depth, count, correct, total = result
    assert success
    assert depth == 0
    assert count >= 2  # birden fazla araç


# ------------------------------------------------------------------
# Senaryo yükleme testi
# ------------------------------------------------------------------

def test_scenarios_load():
    scenarios = load_scenarios()
    assert len(scenarios) >= 3
    for s in scenarios:
        assert "id" in s
        assert "description" in s
        assert "required_agents" in s


@pytest.mark.asyncio
async def test_benchmark_runner():
    collector = MetricsCollector()
    runner = BenchmarkRunner(collector)

    async def dummy_execute(task: str):
        return True, 1, 1, 1, 1

    results = await runner.run_all("test_system", dummy_execute, repeat=1)
    assert len(results) == len(load_scenarios())
    summary = collector.summarize(system="test_system")
    assert summary.task_completion_rate == 1.0
