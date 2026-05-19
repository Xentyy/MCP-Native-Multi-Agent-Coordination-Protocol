"""
BaseAgent — tüm MNACP ajanlarının türediği temel sınıf.

Her somut ajan şunları yapar:
1. define_tools() metodunu override ederek araçlarını bildirir
2. execute_tool() metodunu override ederek araç çağrılarını karşılar
3. start() çağrısı ile registry'ye kaydolur ve MCP sunucuyu ayağa kaldırır
"""
import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID, uuid4

import httpx
from mnacp.agents.base_agent.registry_client import RegistryClient
from mnacp.protocol.schemas import (
    AgentRegistration,
    AgentStatus,
    DelegationRequest,
    DelegationResponse,
    DelegationStatus,
    ToolSchema,
    TrustEvent,
)

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    def __init__(
        self,
        name: str,
        description: str,
        host: str = "localhost",
        port: int = 9000,
        registry_url: str = "http://localhost:8000",
        tags: list[str] | None = None,
        max_delegation_depth: int = 5,
        advertise_host: str | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.host = host
        self.port = port
        # Registry'ye duyurulacak host: 0.0.0.0 dinleniyorsa farklı bir
        # erişilebilir hostname (örn. docker servis adı) verilmeli.
        self.advertise_host = advertise_host or host
        self.registry_url = registry_url
        self.tags = tags or []
        self.max_delegation_depth = max_delegation_depth

        self.agent_id: UUID = uuid4()
        self._registry = RegistryClient(registry_url)
        self._registry_api_key = os.environ.get("REGISTRY_API_KEY", "")
        self._registered = False
        self._running = False
        self._heartbeat_task = None

    # ------------------------------------------------------------------
    # Alt sınıfların override edeceği metodlar
    # ------------------------------------------------------------------

    @abstractmethod
    def define_tools(self) -> list[ToolSchema]:
        """Bu ajanın sunduğu MCP araç listesini döndür."""

    @abstractmethod
    async def execute_tool(self, tool_name: str, parameters: dict[str, Any]) -> Any:
        """Verilen araç adı ve parametrelerle aracı çalıştır."""

    # ------------------------------------------------------------------
    # Yaşam döngüsü
    # ------------------------------------------------------------------

    async def _register_once(self) -> bool:
        try:
            async with self._registry as client:
                registration = AgentRegistration(
                    agent_id=self.agent_id,
                    name=self.name,
                    description=self.description,
                    host=self.advertise_host,
                    port=self.port,
                    tools=self.define_tools(),
                    tags=self.tags,
                    api_key=self._registry_api_key,
                )
                await client.register(registration)
            self._registered = True
            return True
        except Exception as exc:
            logger.warning("Agent '%s' registry kaydı başarısız: %s", self.name, exc)
            return False

    async def _heartbeat_loop(self, interval: float = 15.0) -> None:
        """Registry restart sonrası kayıtları kendiliğinden geri yükle."""
        import asyncio
        while self._running:
            try:
                async with self._registry as client:
                    info = await client.get_agent(self.agent_id)
                if info is None:
                    logger.info("Agent '%s' registry'de bulunamadı, yeniden kaydoluyor", self.name)
                    await self._register_once()
            except Exception as exc:
                logger.debug("heartbeat hatası: %s", exc)
            await asyncio.sleep(interval)

    async def start(self) -> None:
        await self._register_once()
        if self._registered:
            logger.info("Agent '%s' registry'ye kaydedildi (id=%s)", self.name, self.agent_id)
        self._running = True

        import asyncio
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def stop(self) -> None:
        self._running = False
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except Exception:
                pass
            self._heartbeat_task = None
        if self._registered:
            try:
                async with self._registry as client:
                    await client.unregister(self.agent_id)
            except Exception as exc:
                logger.debug("unregister hatası: %s", exc)
            self._registered = False
            logger.info("Agent '%s' registry'den silindi", self.name)

    async def set_status(self, status: AgentStatus) -> None:
        async with self._registry as client:
            await client.update_status(self.agent_id, status)

    # ------------------------------------------------------------------
    # Araç çağrısı (güven skoru ile sarılmış)
    # ------------------------------------------------------------------

    async def call_tool(self, tool_name: str, parameters: dict[str, Any]) -> Any:
        t0 = time.monotonic()
        success = False
        try:
            result = await self.execute_tool(tool_name, parameters)
            success = True
            return result
        except Exception as exc:
            logger.error("Tool '%s' failed: %s", tool_name, exc)
            raise
        finally:
            latency_ms = (time.monotonic() - t0) * 1000
            await self._report_trust(success, latency_ms)

    async def _report_trust(self, success: bool, latency_ms: float) -> None:
        try:
            async with self._registry as client:
                await client.record_trust(TrustEvent(
                    agent_id=self.agent_id,
                    event_type="tool_call",
                    success=success,
                    latency_ms=latency_ms,
                ))
        except Exception:
            pass  # güven kaydı hataları ajanı durdurmamalı

    # ------------------------------------------------------------------
    # Başka bir ajanın aracını uzaktan çağır (MCP benzeri HTTP köprüsü)
    # ------------------------------------------------------------------

    async def call_remote_tool(
        self,
        target_host: str,
        target_port: int,
        tool_name: str,
        parameters: dict[str, Any],
    ) -> Any:
        url = f"http://{target_host}:{target_port}/tools/{tool_name}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=parameters)
            response.raise_for_status()
            return response.json()

    # ------------------------------------------------------------------
    # Delegasyon alma (orkestratörden veya başka ajandan gelen görev)
    # ------------------------------------------------------------------

    async def handle_delegation(self, request: DelegationRequest) -> DelegationResponse:
        if len(request.delegation_chain) >= self.max_delegation_depth:
            return DelegationResponse(
                request_id=request.request_id,
                status=DelegationStatus.REJECTED,
                error=f"Maksimum delegasyon derinliği aşıldı ({self.max_delegation_depth})",
            )

        if self.agent_id in request.delegation_chain:
            return DelegationResponse(
                request_id=request.request_id,
                status=DelegationStatus.REJECTED,
                error="Döngüsel delegasyon tespit edildi",
            )

        try:
            # Delegasyon zincirini context'e ekle — alt ajanlar peer delegasyon için kullanır
            enriched_context = {
                **request.context,
                "_delegation_chain": [str(uid) for uid in request.delegation_chain],
            }
            result = await self._process_delegated_task(request.task, enriched_context)
            return DelegationResponse(
                request_id=request.request_id,
                status=DelegationStatus.COMPLETED,
                result=result,
            )
        except Exception as exc:
            return DelegationResponse(
                request_id=request.request_id,
                status=DelegationStatus.FAILED,
                error=str(exc),
            )

    async def _process_delegated_task(self, task: str, context: dict[str, Any]) -> Any:
        """
        Alt sınıflar bu metodu override edebilir.
        Varsayılan: görev açıklamasına göre en uygun yerel aracı çalıştır.
        """
        tools = self.define_tools()
        if not tools:
            raise ValueError("Bu ajanda hiç araç tanımlı değil")
        # İlk araç basit fallback — orkestratör zaten doğru ajanı seçmeli
        return await self.execute_tool(tools[0].name, context)

    # ------------------------------------------------------------------
    # FastAPI tabanlı MCP benzeri HTTP sunucu
    # ------------------------------------------------------------------

    def build_http_app(self):
        """Bu ajanın araçlarını sunan FastAPI uygulaması döndür."""
        from fastapi import FastAPI, HTTPException, Request

        agent_self = self
        app = FastAPI(title=f"{self.name} MCP Server")

        @app.get("/tools")
        async def list_tools():
            return [t.model_dump() for t in agent_self.define_tools()]

        @app.post("/tools/{tool_name}")
        async def call_tool(tool_name: str, request: Request):
            try:
                body = await request.json()
            except Exception:
                body = {}
            parameters = body.get("parameters", body)
            try:
                result = await agent_self.call_tool(tool_name, parameters)
                return {"result": result}
            except Exception as exc:
                raise HTTPException(status_code=500, detail=str(exc))

        @app.post("/delegate")
        async def delegate(request: Request):
            body = await request.json()
            req_data = body.get("request", body)
            # UUID string → UUID dönüşümü
            from uuid import UUID as _UUID
            for key in ("from_agent_id", "to_agent_id"):
                if key in req_data and isinstance(req_data[key], str):
                    req_data[key] = _UUID(req_data[key])
            chain = req_data.get("delegation_chain", [])
            req_data["delegation_chain"] = [
                _UUID(x) if isinstance(x, str) else x for x in chain
            ]
            delegation_req = DelegationRequest(**req_data)
            result = await agent_self.handle_delegation(delegation_req)
            return result.model_dump(mode="json")

        @app.get("/health")
        async def health():
            return {"agent_id": str(agent_self.agent_id), "name": agent_self.name, "status": "ok"}

        return app

    async def serve(self) -> None:
        """start() sonrası HTTP sunucuyu çalıştır (blocking)."""
        import uvicorn
        app = self.build_http_app()
        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="warning")
        server = uvicorn.Server(config)
        await server.serve()

    async def run(self) -> None:
        """Kaydol + HTTP sunucuyu başlat (tek adımda)."""
        await self.start()
        try:
            await self.serve()
        finally:
            await self.stop()
