"""
Ana evaluation scripti — 3 sistemi senaryolar üzerinde çalıştırır,
metrikleri toplar, grafik üretir, JSON özet kaydeder.

Kullanım:
    python -m mnacp.evaluation.run_evaluation
    python -m mnacp.evaluation.run_evaluation --repeat 5
    python -m mnacp.evaluation.run_evaluation --skip-mnacp  (sadece baseline)
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import sys
import time
from pathlib import Path

# Windows konsolu Unicode için UTF-8'e çevir
if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from mnacp.evaluation.benchmarks.task_suite import BenchmarkRunner, load_scenarios
from mnacp.evaluation.metrics import MetricsCollector
from mnacp.evaluation.plots import generate_all_plots
from mnacp.evaluation.runners import (
    make_central_runner,
    make_mnacp_runner,
    make_static_runner,
)

OUTPUT_DIR = Path(__file__).parent / "results"


async def run_system_on_scenarios(
    collector: MetricsCollector,
    system_name: str,
    runner_factory,
    scenarios: list[dict],
    repeat: int,
) -> None:
    """Bir sistemi tüm senaryolarda repeat kez çalıştır."""
    runner = BenchmarkRunner(collector)
    print(f"\n=== {system_name} ===")
    for scenario in scenarios:
        print(f"  [{scenario['id']}] {scenario['description'][:60]}...")
        execute_fn = runner_factory(scenario)
        for i in range(repeat):
            t0 = time.monotonic()
            result = await runner.run_scenario(scenario, system_name, execute_fn)
            elapsed = time.monotonic() - t0
            status = "[OK]" if result.success else "[FAIL]"
            print(
                f"    {status} tekrar {i + 1}/{repeat} "
                f"({elapsed:.2f}s, depth={result.delegation_depth}, "
                f"correct={result.correct_agent_selections}/{result.total_agent_selections})"
            )


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat", type=int, default=3, help="Senaryo başına tekrar")
    parser.add_argument("--skip-mnacp", action="store_true", help="MNACP'yi atla (HTTP yoksa)")
    parser.add_argument("--only-mnacp", action="store_true", help="Sadece MNACP")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    scenarios = load_scenarios()
    print(f"Yüklenen senaryo sayısı: {len(scenarios)}")
    print(f"Tekrar sayısı: {args.repeat}")

    collector = MetricsCollector()

    if not args.skip_mnacp:
        await run_system_on_scenarios(
            collector, "mnacp", make_mnacp_runner, scenarios, args.repeat,
        )

    if not args.only_mnacp:
        await run_system_on_scenarios(
            collector, "baseline_static", make_static_runner, scenarios, args.repeat,
        )
        await run_system_on_scenarios(
            collector, "baseline_central", make_central_runner, scenarios, args.repeat,
        )

    print("\n" + "=" * 60)
    print("ÖZET")
    print("=" * 60)
    summaries = {}
    for sys_name in collector.all_systems():
        summary = collector.summarize(system=sys_name)
        if summary is None:
            continue
        summaries[sys_name] = {
            "task_completion_rate": summary.task_completion_rate,
            "delegation_accuracy": summary.delegation_accuracy,
            "avg_delegation_depth": summary.avg_delegation_depth,
            "avg_delegation_count": summary.avg_delegation_count,
            "p50_latency_ms": summary.p50_latency_ms,
            "p90_latency_ms": summary.p90_latency_ms,
            "p99_latency_ms": summary.p99_latency_ms,
            "deadlock_rate": summary.deadlock_rate,
            "total_runs": summary.total_runs,
        }
        print(f"\n{sys_name}:")
        for k, v in summaries[sys_name].items():
            print(f"  {k}: {v}")

    # JSON çıktı
    summary_path = OUTPUT_DIR / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summaries, f, indent=2, ensure_ascii=False)
    print(f"\nÖzet: {summary_path}")

    # Ham veri (her tekrar)
    raw_path = OUTPUT_DIR / "raw_results.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(collector.export(), f, indent=2, ensure_ascii=False, default=str)
    print(f"Ham veri: {raw_path}")

    # Grafikler
    print()
    generate_all_plots(collector, OUTPUT_DIR)
    print(f"\nTüm çıktılar: {OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
