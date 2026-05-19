"""
Evaluation grafikleri — matplotlib ile PNG üretir.

3 grafik:
- görev tamamlama oranı (bar)
- gecikme dağılımı (P50/P90/P99 yan yana bar)
- senaryo × sistem ısı haritası
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from mnacp.evaluation.metrics import MetricsCollector

SYSTEM_LABELS = {
    "mnacp": "MNACP (bizim)",
    "baseline_static": "Statik Atama",
    "baseline_central": "Merkezi (delegasyonsuz)",
}

SYSTEM_COLORS = {
    "mnacp": "#6366f1",
    "baseline_static": "#94a3b8",
    "baseline_central": "#f59e0b",
}


def plot_task_completion(collector: MetricsCollector, output: Path) -> None:
    """Sistem başına görev tamamlama oranı bar chart'ı."""
    systems = sorted(collector.all_systems())
    rates = []
    labels = []
    colors = []

    for sys_name in systems:
        summary = collector.summarize(system=sys_name)
        if summary is None:
            continue
        rates.append(summary.task_completion_rate * 100)
        labels.append(SYSTEM_LABELS.get(sys_name, sys_name))
        colors.append(SYSTEM_COLORS.get(sys_name, "#888888"))

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(labels, rates, color=colors, edgecolor="#1e293b", linewidth=1.5)
    ax.set_ylim(0, 105)
    ax.set_ylabel("Görev Tamamlama Oranı (%)", fontsize=12)
    ax.set_title("Sistem Karşılaştırması — Görev Tamamlama Oranı", fontsize=14, pad=15)
    ax.grid(axis="y", alpha=0.3, linestyle="--")

    for bar, rate in zip(bars, rates):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 2,
            f"{rate:.1f}%",
            ha="center", va="bottom", fontsize=11, fontweight="bold",
        )

    plt.tight_layout()
    plt.savefig(output, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"  [OK] {output.name}")


def plot_latency_distribution(collector: MetricsCollector, output: Path) -> None:
    """P50/P90/P99 gecikme grafiği — yan yana 3 bar grubu."""
    systems = sorted(collector.all_systems())
    percentiles = ["P50", "P90", "P99"]

    data: dict[str, list[float]] = {}
    for sys_name in systems:
        summary = collector.summarize(system=sys_name)
        if summary is None:
            continue
        data[sys_name] = [
            summary.p50_latency_ms,
            summary.p90_latency_ms,
            summary.p99_latency_ms,
        ]

    x = np.arange(len(percentiles))
    width = 0.25

    fig, ax = plt.subplots(figsize=(10, 5.5))
    for i, (sys_name, latencies) in enumerate(data.items()):
        offset = (i - len(data) / 2 + 0.5) * width
        ax.bar(
            x + offset, latencies, width,
            label=SYSTEM_LABELS.get(sys_name, sys_name),
            color=SYSTEM_COLORS.get(sys_name, "#888"),
            edgecolor="#1e293b", linewidth=1.2,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(percentiles)
    ax.set_ylabel("Gecikme (ms)", fontsize=12)
    ax.set_title("Sistem Karşılaştırması — Gecikme Dağılımı", fontsize=14, pad=15)
    ax.legend(loc="upper left")
    ax.grid(axis="y", alpha=0.3, linestyle="--")

    plt.tight_layout()
    plt.savefig(output, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"  [OK] {output.name}")


def plot_scenario_heatmap(collector: MetricsCollector, output: Path) -> None:
    """Senaryo × sistem matrisi — hücreler tamamlama oranı."""
    systems = sorted(collector.all_systems())
    scenarios = sorted(collector.all_scenarios())

    matrix = np.zeros((len(scenarios), len(systems)))
    for i, scn in enumerate(scenarios):
        for j, sys_name in enumerate(systems):
            summary = collector.summarize(system=sys_name, scenario_id=scn)
            matrix[i, j] = summary.task_completion_rate * 100 if summary else 0.0

    fig, ax = plt.subplots(figsize=(8, max(4, len(scenarios) * 0.7)))
    im = ax.imshow(matrix, cmap="RdYlGn", vmin=0, vmax=100, aspect="auto")

    ax.set_xticks(np.arange(len(systems)))
    ax.set_xticklabels(
        [SYSTEM_LABELS.get(s, s) for s in systems],
        rotation=20, ha="right",
    )
    ax.set_yticks(np.arange(len(scenarios)))
    ax.set_yticklabels(scenarios)

    for i in range(len(scenarios)):
        for j in range(len(systems)):
            value = matrix[i, j]
            color = "white" if value < 50 else "#0f172a"
            ax.text(
                j, i, f"{value:.0f}%",
                ha="center", va="center", color=color, fontsize=11, fontweight="bold",
            )

    ax.set_title("Senaryo Bazlı Performans (görev tamamlama %)", fontsize=14, pad=15)
    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("Tamamlama Oranı (%)", fontsize=10)

    plt.tight_layout()
    plt.savefig(output, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"  [OK] {output.name}")


def generate_all_plots(collector: MetricsCollector, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Grafikler {output_dir} dizinine yazılıyor:")
    plot_task_completion(collector, output_dir / "completion_rate.png")
    plot_latency_distribution(collector, output_dir / "latency_distribution.png")
    plot_scenario_heatmap(collector, output_dir / "scenario_heatmap.png")
