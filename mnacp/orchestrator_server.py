"""
Orkestratör HTTP sunucusu.

Frontend'in /monitor sayfası bu API'ya bağlanır (localhost:8002).
Kullanıcıdan görev alır, orkestratöre iletir, sonuçları ve geçmişi sunar.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from collections import defaultdict

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()

from mnacp.agents.orchestrator.agent import OrchestratorAgent  # noqa: E402

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

app = FastAPI(title="MNACP Orchestrator", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = OrchestratorAgent(
    registry_url=os.environ.get("NEXT_PUBLIC_REGISTRY_URL", "http://localhost:8000"),
    model=os.environ.get("ORCHESTRATOR_MODEL", "claude-sonnet-4-5"),
)


class RunTaskRequest(BaseModel):
    task: str


class RunTaskResponse(BaseModel):
    result: str
    stats: dict | None = None


@app.post("/run", response_model=RunTaskResponse)
async def run_task(body: RunTaskRequest) -> RunTaskResponse:
    """Görevi orkestratöre gönder ve sonucu döndür."""
    logger.info("Görev alındı: %s", body.task[:80])
    result = await orchestrator.run(body.task)
    stats = orchestrator.get_stats()
    return RunTaskResponse(result=result, stats=stats)


@app.post("/run/stream")
async def run_task_stream(body: RunTaskRequest) -> StreamingResponse:
    """Görevi çalıştırırken her aşama için SSE event yayınla."""
    logger.info("Stream görevi alındı: %s", body.task[:80])
    queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def emit(event: dict) -> None:
        await queue.put(event)

    async def runner() -> None:
        try:
            await orchestrator.run(body.task, on_event=emit)
        except Exception as exc:  # pragma: no cover
            await queue.put({"type": "error", "message": str(exc)})
        finally:
            await queue.put(None)

    async def event_generator():
        task = asyncio.create_task(runner())
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/stats")
async def get_stats() -> dict:
    """Delegasyon istatistiklerini döndür."""
    return orchestrator.get_stats()


@app.get("/history")
async def get_history() -> list[dict]:
    """Delegasyon geçmişini döndür."""
    return orchestrator.get_delegation_history()


@app.get("/stats/by_agent")
async def stats_by_agent() -> list[dict]:
    """Her hedef ajan için kırılımlı istatistik döndür.

    Frontend'in monitor sayfasındaki ajan bazlı bar chart için.
    """
    history = orchestrator.get_delegation_history()
    bucket: dict[str, dict] = defaultdict(
        lambda: {"agent_id": "", "total": 0, "completed": 0, "failed": 0,
                 "rejected": 0, "total_latency_ms": 0.0, "name": ""},
    )
    # Registry'den ajan isimleri ve trend bilgisi al
    import httpx
    name_map: dict[str, str] = {}
    trend_map: dict[str, str] = {}
    registry_base = os.environ.get("NEXT_PUBLIC_REGISTRY_URL", "http://localhost:8000")
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            agents_r, trends_r = await asyncio.gather(
                c.get(f"{registry_base}/agents"),
                c.get(f"{registry_base}/agents/trends"),
                return_exceptions=True,
            )
            if not isinstance(agents_r, Exception) and agents_r.status_code == 200:
                for a in agents_r.json():
                    name_map[a["agent_id"]] = a["name"]
            if not isinstance(trends_r, Exception) and trends_r.status_code == 200:
                trend_map = trends_r.json()
    except Exception:
        pass

    for entry in history:
        to_id = entry.get("to", "")
        b = bucket[to_id]
        b["agent_id"] = to_id
        b["name"] = name_map.get(to_id, to_id[:8] + "…")
        b["total"] += 1
        b["total_latency_ms"] += entry.get("latency_ms", 0.0)
        status = entry.get("status", "")
        if status == "completed":
            b["completed"] += 1
        elif status == "failed":
            b["failed"] += 1
        elif status == "rejected":
            b["rejected"] += 1

    result = []
    for b in bucket.values():
        if b["total"] == 0:
            continue
        result.append({
            "agent_id": b["agent_id"],
            "name": b["name"],
            "total": b["total"],
            "completed": b["completed"],
            "failed": b["failed"],
            "rejected": b["rejected"],
            "success_rate": round(b["completed"] / b["total"], 3),
            "avg_latency_ms": round(b["total_latency_ms"] / b["total"], 1),
            "trend": trend_map.get(b["agent_id"], "stable"),
        })
    result.sort(key=lambda x: x["total"], reverse=True)
    return result


@app.get("/stats/timeseries")
async def stats_timeseries() -> list[dict]:
    """Son 60 delegasyonu 1 dakikalık bucket'lara böl.

    Frontend'in monitor sayfasındaki AreaChart için kullanılır.
    Her bucket: {minute, count, success_count, avg_latency_ms}
    """
    from datetime import datetime
    history = orchestrator.get_delegation_history()

    buckets: dict[str, dict] = {}
    for entry in history:
        ts_raw = entry.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_raw)
        except Exception:
            continue
        # Dakika başına yuvarla (saniyeyi sıfırla)
        minute_key = ts.strftime("%Y-%m-%dT%H:%M")
        if minute_key not in buckets:
            buckets[minute_key] = {"minute": minute_key, "count": 0, "success_count": 0, "total_latency_ms": 0.0}
        b = buckets[minute_key]
        b["count"] += 1
        b["total_latency_ms"] += entry.get("latency_ms", 0.0)
        if entry.get("status") == "completed":
            b["success_count"] += 1

    result = []
    for b in sorted(buckets.values(), key=lambda x: x["minute"]):
        result.append({
            "minute": b["minute"],
            "count": b["count"],
            "success_count": b["success_count"],
            "avg_latency_ms": round(b["total_latency_ms"] / b["count"], 1) if b["count"] else 0,
        })
    return result[-60:]  # Son 60 dakika


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "agent_id": str(orchestrator.agent_id)}


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("ORCHESTRATOR_PORT", 8002))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
