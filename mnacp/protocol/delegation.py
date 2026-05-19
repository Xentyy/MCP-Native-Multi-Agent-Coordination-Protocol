"""
Delegasyon Protokolü — projenin kalbi.

DelegationManager:
- Delegasyon kararı verir
- Güvenlik kontrollerini (döngü, derinlik) uygular
- Uzak ajana HTTP üzerinden görevi iletir
- Sonucu geri döndürür
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import httpx
from mnacp.protocol.deadlock_detector import DeadlockDetector
from mnacp.protocol.schemas import (
    DelegationRequest,
    DelegationResponse,
    DelegationStatus,
)

logger = logging.getLogger(__name__)

DEFAULT_MAX_DEPTH = 5


class DelegationError(Exception):
    pass


class DelegationManager:
    """
    Delegasyon yaşam döngüsünü yönetir.

    Kullanım:
        manager = DelegationManager()
        response = await manager.delegate(
            from_agent_id=...,
            to_agent_host="localhost",
            to_agent_port=9001,
            to_agent_id=...,
            task="...",
            context={},
            chain=[],
        )
    """

    def __init__(self, max_depth: int = DEFAULT_MAX_DEPTH) -> None:
        self.max_depth = max_depth
        self._detector = DeadlockDetector()
        self._active: dict[str, DelegationRequest] = {}
        self._history: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Ana delegasyon metodu
    # ------------------------------------------------------------------

    async def delegate(
        self,
        from_agent_id: UUID,
        to_agent_id: UUID,
        to_agent_host: str,
        to_agent_port: int,
        task: str,
        context: dict[str, Any] | None = None,
        chain: list[UUID] | None = None,
        to_agent_base_path: str = "",
    ) -> DelegationResponse:
        chain = chain or []
        context = context or {}

        # --- Güvenlik kontrolleri ---
        if len(chain) >= self.max_depth:
            resp = DelegationResponse(
                request_id=uuid4(),
                status=DelegationStatus.REJECTED,
                error=f"Maksimum delegasyon derinliği ({self.max_depth}) aşıldı",
                completed_at=datetime.utcnow(),
            )
            self._record_history(
                DelegationRequest(
                    from_agent_id=from_agent_id, to_agent_id=to_agent_id,
                    task=task, context=context, delegation_chain=chain,
                ),
                resp, 0.0,
            )
            return resp

        safe, reason = self._detector.is_safe_to_delegate(from_agent_id, to_agent_id, chain)
        if not safe:
            resp = DelegationResponse(
                request_id=uuid4(),
                status=DelegationStatus.REJECTED,
                error=reason,
                completed_at=datetime.utcnow(),
            )
            self._record_history(
                DelegationRequest(
                    from_agent_id=from_agent_id, to_agent_id=to_agent_id,
                    task=task, context=context, delegation_chain=chain,
                ),
                resp, 0.0,
            )
            return resp

        # --- İstek oluştur ---
        request = DelegationRequest(
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            task=task,
            context=context,
            delegation_chain=chain + [from_agent_id],
            max_depth=self.max_depth,
        )

        rid = str(request.request_id)
        self._active[rid] = request
        self._detector.add_delegation(from_agent_id, to_agent_id)

        t0 = time.monotonic()
        try:
            response = await self._send_delegation(request, to_agent_host, to_agent_port, to_agent_base_path)
            response.completed_at = datetime.utcnow()
        except Exception as exc:
            response = DelegationResponse(
                request_id=request.request_id,
                status=DelegationStatus.FAILED,
                error=str(exc),
                completed_at=datetime.utcnow(),
            )
        finally:
            self._active.pop(rid, None)
            self._detector.remove_delegation(from_agent_id, to_agent_id)
            latency_ms = (time.monotonic() - t0) * 1000
            self._record_history(request, response, latency_ms)

        return response

    # ------------------------------------------------------------------
    # HTTP üzerinden ajan'a delegasyon gönder
    # ------------------------------------------------------------------

    @staticmethod
    async def _send_delegation(
        request: DelegationRequest,
        host: str,
        port: int,
        base_path: str = "",
    ) -> DelegationResponse:
        path = base_path.rstrip("/") + "/delegate" if base_path else "/delegate"
        url = f"http://{host}:{port}{path}"
        payload = {"request": request.model_dump(mode="json")}

        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            return DelegationResponse.model_validate(r.json())

    # ------------------------------------------------------------------
    # Geçmiş ve durum
    # ------------------------------------------------------------------

    def _record_history(
        self,
        request: DelegationRequest,
        response: DelegationResponse,
        latency_ms: float,
    ) -> None:
        self._history.append({
            "request_id": str(request.request_id),
            "from": str(request.from_agent_id),
            "to": str(request.to_agent_id),
            "task": request.task[:80],
            "chain_depth": len(request.delegation_chain),
            "status": response.status.value,
            "latency_ms": round(latency_ms, 2),
            "timestamp": datetime.utcnow().isoformat(),
        })

    def get_history(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._history[-limit:]

    def get_active(self) -> list[DelegationRequest]:
        return list(self._active.values())

    def get_stats(self) -> dict[str, Any]:
        if not self._history:
            return {"total": 0}
        total = len(self._history)
        completed = sum(1 for h in self._history if h["status"] == "completed")
        rejected = sum(1 for h in self._history if h["status"] == "rejected")
        failed = sum(1 for h in self._history if h["status"] == "failed")
        latencies = [h["latency_ms"] for h in self._history]
        depths = [h["chain_depth"] for h in self._history]
        return {
            "total": total,
            "completed": completed,
            "rejected": rejected,
            "failed": failed,
            "success_rate": round(completed / total, 3),
            "avg_latency_ms": round(sum(latencies) / len(latencies), 2),
            "avg_depth": round(sum(depths) / len(depths), 2),
            "max_depth": max(depths),
        }


# ------------------------------------------------------------------
# Modül düzeyinde singleton — orkestratör bu nesneyi kullanır
# ------------------------------------------------------------------
delegation_manager = DelegationManager()
