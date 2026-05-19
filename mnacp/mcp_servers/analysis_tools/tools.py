"""Trend analizi, karşılaştırma ve raporlama araçları."""
from __future__ import annotations

import statistics
from typing import Any

from pydantic import BaseModel, Field


class TrendAnalysisParams(BaseModel):
    values: list[float] = Field(description="Zaman serisi değerleri (eski→yeni)")
    window: int = Field(default=3, ge=2, description="Hareketli ortalama penceresi")


class CompareParams(BaseModel):
    baseline: dict[str, float] = Field(description="Referans metrikler")
    current: dict[str, float] = Field(description="Güncel metrikler")


class GenerateReportParams(BaseModel):
    title: str = Field(description="Rapor başlığı")
    sections: list[dict[str, Any]] = Field(description="[{heading, content}] listesi")
    format: str = Field(default="markdown", description="markdown | text")


class CorrelationParams(BaseModel):
    x: list[float] = Field(description="X değerleri")
    y: list[float] = Field(description="Y değerleri")


def trend_analysis(params: TrendAnalysisParams) -> dict[str, Any]:
    vals = params.values
    if len(vals) < 2:
        return {"trend": "insufficient_data"}

    # Hareketli ortalama
    w = params.window
    ma = [statistics.mean(vals[i : i + w]) for i in range(len(vals) - w + 1)]

    # Basit doğrusal eğim (en küçük kareler)
    n = len(vals)
    x_mean = (n - 1) / 2
    y_mean = statistics.mean(vals)
    num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(vals))
    den = sum((i - x_mean) ** 2 for i in range(n))
    slope = num / den if den != 0 else 0

    return {
        "slope": round(slope, 4),
        "trend": "up" if slope > 0.01 else "down" if slope < -0.01 else "flat",
        "moving_average": [round(v, 4) for v in ma],
        "first_value": vals[0],
        "last_value": vals[-1],
        "change_pct": round((vals[-1] - vals[0]) / (abs(vals[0]) + 1e-9) * 100, 2),
    }


def compare(params: CompareParams) -> dict[str, Any]:
    result = {}
    all_keys = set(params.baseline) | set(params.current)
    for k in all_keys:
        base = params.baseline.get(k)
        curr = params.current.get(k)
        if base is not None and curr is not None:
            delta = curr - base
            pct = delta / (abs(base) + 1e-9) * 100
            result[k] = {
                "baseline": base,
                "current": curr,
                "delta": round(delta, 4),
                "change_pct": round(pct, 2),
                "direction": "up" if delta > 0 else "down" if delta < 0 else "same",
                "status": "changed" if delta != 0 else "same",
            }
        else:
            result[k] = {"baseline": base, "current": curr, "status": "missing"}
    return result


def generate_report(params: GenerateReportParams) -> str:
    if params.format == "markdown":
        lines = [f"# {params.title}", ""]
        for sec in params.sections:
            lines.append(f"## {sec.get('heading', 'Bölüm')}")
            lines.append("")
            content = sec.get("content", "")
            if isinstance(content, dict):
                for k, v in content.items():
                    lines.append(f"- **{k}**: {v}")
            elif isinstance(content, list):
                for item in content:
                    lines.append(f"- {item}")
            else:
                lines.append(str(content))
            lines.append("")
        return "\n".join(lines)
    else:
        parts = [params.title, "=" * len(params.title)]
        for sec in params.sections:
            parts.append(f"\n{sec.get('heading', '')}")
            parts.append(str(sec.get("content", "")))
        return "\n".join(parts)


def correlation(params: CorrelationParams) -> dict[str, float]:
    x, y = params.x, params.y
    n = min(len(x), len(y))
    if n < 2:
        return {"pearson_r": 0.0, "n": n}
    x, y = x[:n], y[:n]
    xm, ym = statistics.mean(x), statistics.mean(y)
    num = sum((xi - xm) * (yi - ym) for xi, yi in zip(x, y))
    den = (sum((xi - xm) ** 2 for xi in x) * sum((yi - ym) ** 2 for yi in y)) ** 0.5
    r = num / den if den != 0 else 0.0
    return {"pearson_r": round(r, 4), "n": n}


TOOL_HANDLERS: dict[str, tuple[type[BaseModel], Any]] = {
    "trend_analysis": (TrendAnalysisParams, trend_analysis),
    "compare": (CompareParams, compare),
    "generate_report": (GenerateReportParams, generate_report),
    "correlation": (CorrelationParams, correlation),
}
