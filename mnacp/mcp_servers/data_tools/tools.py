"""Veri işleme MCP araçları — tip güvenli Pydantic şemaları ile."""
from __future__ import annotations

import csv
import io
import statistics
from typing import Any

from pydantic import BaseModel, Field


class LoadCsvParams(BaseModel):
    content: str = Field(description="CSV dosyasının metin içeriği")
    delimiter: str = Field(default=",", description="Sütun ayırıcı karakter")


class CleanDataParams(BaseModel):
    rows: list[dict[str, Any]] = Field(description="Ham satır listesi")
    drop_empty: bool = Field(default=True, description="Boş değer içeren satırları sil")
    strip_whitespace: bool = Field(default=True, description="Boşlukları temizle")


class ComputeStatisticsParams(BaseModel):
    rows: list[dict[str, Any]] = Field(description="Satır listesi")
    column: str = Field(description="İstatistik hesaplanacak sütun adı")


class FilterRowsParams(BaseModel):
    rows: list[dict[str, Any]] = Field(description="Satır listesi")
    column: str = Field(description="Filtre uygulanacak sütun")
    value: str = Field(description="Eşleştirilecek değer")
    operator: str = Field(default="eq", description="eq | neq | gt | lt | contains")


def load_csv(params: LoadCsvParams) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(params.content), delimiter=params.delimiter)
    return [dict(row) for row in reader]


def clean_data(params: CleanDataParams) -> list[dict[str, Any]]:
    result = []
    for row in params.rows:
        if params.strip_whitespace:
            row = {k.strip(): v.strip() if isinstance(v, str) else v for k, v in row.items()}
        if params.drop_empty and any(v in (None, "", "null", "NULL") for v in row.values()):
            continue
        result.append(row)
    return result


def compute_statistics(params: ComputeStatisticsParams) -> dict[str, float]:
    values = []
    for row in params.rows:
        raw = row.get(params.column)
        if raw is None:
            continue
        try:
            values.append(float(raw))
        except (ValueError, TypeError):
            continue

    if not values:
        return {"error": -1, "count": 0}

    return {
        "count": len(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
    }


def filter_rows(params: FilterRowsParams) -> list[dict[str, Any]]:
    result = []
    for row in params.rows:
        cell = str(row.get(params.column, ""))
        try:
            cell_num = float(cell)
            val_num = float(params.value)
        except (ValueError, TypeError):
            cell_num = val_num = None

        match params.operator:
            case "eq":
                keep = cell == params.value
            case "neq":
                keep = cell != params.value
            case "gt":
                keep = cell_num is not None and cell_num > val_num
            case "lt":
                keep = cell_num is not None and cell_num < val_num
            case "contains":
                keep = params.value.lower() in cell.lower()
            case _:
                keep = False

        if keep:
            result.append(row)
    return result


# Araç kataloğu — MCP sunucu ve BaseAgent her ikisi de bunu kullanır
TOOL_HANDLERS: dict[str, tuple[type[BaseModel], Any]] = {
    "load_csv": (LoadCsvParams, load_csv),
    "clean_data": (CleanDataParams, clean_data),
    "compute_statistics": (ComputeStatisticsParams, compute_statistics),
    "filter_rows": (FilterRowsParams, filter_rows),
}
