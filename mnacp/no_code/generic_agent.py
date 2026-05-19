"""
GenericAgent — No-code rol oluşturucunun ürettiği ajanlar için evrensel backend.

Claude API'yı kullanarak tool çağrılarını doğal dil ile karşılar.
Role-builder'ın FastAPI app'ine sub-path olarak mount edilir;
ayrı bir port/container gerektirmez.
"""
from __future__ import annotations

import logging
import os
from typing import Any
from uuid import UUID, uuid4

import anthropic
from mnacp.no_code.role_builder import RoleProposal
from mnacp.protocol.schemas import (
    AgentRegistration,
    DelegationRequest,
    DelegationResponse,
    DelegationStatus,
    ToolSchema,
)

logger = logging.getLogger(__name__)

TOOL_SYSTEM = """\
Sen "{agent_name}" adlı bir yapay zeka ajanısın.
Görevin: {agent_description}

Sana bir tool çağrısı geliyor. Parametreleri kullanarak görevi yap ve SADECE
sonucu JSON olarak döndür. Açıklama, özür veya yorum ekleme — sadece JSON.
"""

DELEGATION_SYSTEM = """\
Sen "{agent_name}" adlı bir yapay zeka ajanısın.
Görevin: {agent_description}

Sana bir görev delege edildi. Elindeki araçları kullanarak görevi tamamla ve
sonucu JSON formatında döndür. Kısa, net ve yapılandırılmış yanıt ver.
"""


class GenericAgent:
    """Claude-backed evrensel ajan. Role-builder'ın ürettiği her rol için kullanılır."""

    def __init__(
        self,
        proposal: RoleProposal,
        agent_id: UUID | None = None,
        registry_host: str = "localhost",
        registry_port: int = 8001,
        model: str = "claude-haiku-4-5-20251001",
    ) -> None:
        self.agent_id: UUID = agent_id or uuid4()
        self.proposal = proposal
        self.name = proposal.agent_name
        self.description = proposal.agent_description
        self._registry_host = registry_host
        self._registry_port = registry_port
        self._model = model
        self._client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.max_delegation_depth = 5

    # ------------------------------------------------------------------
    # Tool çalıştırma — Claude ile
    # ------------------------------------------------------------------

    def execute_tool_sync(self, tool_name: str, parameters: dict[str, Any]) -> Any:
        tool = next((t for t in self.proposal.tools if t.name == tool_name), None)
        if tool is None:
            return {"error": f"Bilinmeyen araç: {tool_name}"}

        system = TOOL_SYSTEM.format(
            agent_name=self.name,
            agent_description=self.description,
        )
        user_msg = (
            f"Araç: {tool_name}\n"
            f"Açıklama: {tool.description}\n"
            f"Parametreler: {parameters}"
        )
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=512,
                system=system,
                messages=[{"role": "user", "content": user_msg}],
            )
            import json
            raw = response.content[0].text.strip()
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"result": raw}
        except Exception as exc:
            logger.error("GenericAgent tool hatası (%s): %s", tool_name, exc)
            return {"error": str(exc)}

    # ------------------------------------------------------------------
    # Delegasyon alma
    # ------------------------------------------------------------------

    def handle_delegation_sync(self, request: DelegationRequest) -> DelegationResponse:
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

        tools_desc = "\n".join(
            f"- {t.name}: {t.description}" for t in self.proposal.tools
        )
        system = DELEGATION_SYSTEM.format(
            agent_name=self.name,
            agent_description=self.description,
        )
        user_msg = (
            f"Görev: {request.task}\n"
            f"Bağlam: {request.context}\n\n"
            f"Kullanabileceğin araçlar:\n{tools_desc}"
        )
        try:
            import json
            response = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=system,
                messages=[{"role": "user", "content": user_msg}],
            )
            raw = response.content[0].text.strip()
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            try:
                result = json.loads(raw)
            except json.JSONDecodeError:
                result = {"result": raw}

            return DelegationResponse(
                request_id=request.request_id,
                status=DelegationStatus.COMPLETED,
                result=result,
            )
        except Exception as exc:
            logger.error("GenericAgent delegasyon hatası: %s", exc)
            return DelegationResponse(
                request_id=request.request_id,
                status=DelegationStatus.FAILED,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Registry kaydı için schema
    # ------------------------------------------------------------------

    def to_registration(self) -> AgentRegistration:
        return AgentRegistration(
            agent_id=self.agent_id,
            name=self.name,
            description=self.description,
            host=self._registry_host,
            port=self._registry_port,
            base_path=f"/agents/{self.agent_id}",
            tools=[
                ToolSchema(
                    name=t.name,
                    description=t.description,
                    parameters=t.parameters,
                )
                for t in self.proposal.tools
            ],
            tags=self.proposal.tags,
        )
