"""
No-Code Rol Oluşturucu.

Kullanıcının doğal dil açıklamasından (örn. "finansal raporları analiz eden bir ajan")
MCP araç listesi önerir ve onay sonrası ajanı registry'ye kaydeder.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field

import anthropic
from mnacp.agents.base_agent.registry_client import RegistryClient
from mnacp.protocol.schemas import AgentInfo, AgentRegistration, ToolSchema

logger = logging.getLogger(__name__)

SUGGEST_SYSTEM = """Sen bir çok-ajanlı sistem tasarımcısısın.
Kullanıcı senden yeni bir ajan rolü tanımlamanı istiyor.
Açıklamaya göre bu ajanın hangi MCP araçlarına sahip olması gerektiğini öner.

SADECE aşağıdaki JSON formatında yanıt ver, başka hiçbir şey yazma:
{
  "agent_name": "MyAgent",
  "agent_description": "Bu ajanın ne yaptığının özlü açıklaması",
  "tags": ["tag1", "tag2"],
  "tools": [
    {
      "name": "tool_snake_case",
      "description": "Aracın ne yaptığı",
      "parameters": {"param1": "string", "param2": "integer"}
    }
  ],
  "rationale": "Bu araçları neden önerdiğinin kısa açıklaması"
}

Kurallar:
- Araç isimleri snake_case olmalı
- En az 2, en fazla 6 araç öner
- Her araç gerçekten bu ajan tarafından yapılabilir işler olmalı
- Araç açıklamaları net ve spesifik olmalı
"""


@dataclass
class ToolSuggestion:
    name: str
    description: str
    parameters: dict[str, str] = field(default_factory=dict)


@dataclass
class RoleProposal:
    agent_name: str
    agent_description: str
    tags: list[str]
    tools: list[ToolSuggestion]
    rationale: str
    user_description: str


class RoleBuilder:
    def __init__(
        self,
        registry_url: str = "http://localhost:8000",
        model: str = "claude-sonnet-4-5",
        default_host: str = "localhost",
        default_port_start: int = 9100,
    ) -> None:
        self._client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self._model = model
        self._registry_url = registry_url
        self._default_host = default_host
        self._next_port = default_port_start

    async def suggest(self, user_description: str) -> RoleProposal:
        """Kullanıcı açıklamasından araç önerileri üret."""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._suggest_sync, user_description)

    def _suggest_sync(self, user_description: str) -> RoleProposal:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=SUGGEST_SYSTEM,
            messages=[{"role": "user", "content": f"Rol açıklaması: {user_description}"}],
        )
        raw = response.content[0].text.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("RoleBuilder JSON parse hatası, fallback kullanılıyor")
            data = {
                "agent_name": "CustomAgent",
                "agent_description": user_description,
                "tags": [],
                "tools": [{"name": "custom_tool", "description": user_description, "parameters": {}}],
                "rationale": "Otomatik oluşturuldu",
            }

        tools = [ToolSuggestion(**t) for t in data.get("tools", [])]
        return RoleProposal(
            agent_name=data.get("agent_name", "CustomAgent"),
            agent_description=data.get("agent_description", user_description),
            tags=data.get("tags", []),
            tools=tools,
            rationale=data.get("rationale", ""),
            user_description=user_description,
        )

    async def create_agent(
        self,
        proposal: RoleProposal,
        host: str | None = None,
        port: int | None = None,
    ) -> AgentInfo:
        """Onaylanan teklifi registry'ye kaydet."""
        tool_schemas = [
            ToolSchema(
                name=t.name,
                description=t.description,
                parameters=t.parameters,
            )
            for t in proposal.tools
        ]

        registration = AgentRegistration(
            name=proposal.agent_name,
            description=proposal.agent_description,
            host=host or self._default_host,
            port=port or self._next_port,
            tools=tool_schemas,
            tags=proposal.tags,
        )
        self._next_port += 1

        async with RegistryClient(self._registry_url) as client:
            info = await client.register(registration)
            logger.info("No-code ajan oluşturuldu: %s (id=%s)", info.name, info.agent_id)
            return info

    @staticmethod
    def format_proposal(proposal: RoleProposal) -> str:
        """Teklifi kullanıcıya göstermek için biçimlendir."""
        lines = [
            f"Ajan Adı   : {proposal.agent_name}",
            f"Açıklama   : {proposal.agent_description}",
            f"Etiketler  : {', '.join(proposal.tags) or '-'}",
            f"Gerekçe    : {proposal.rationale}",
            "",
            "Önerilen Araçlar:",
        ]
        for i, tool in enumerate(proposal.tools, 1):
            lines.append(f"  {i}. {tool.name}")
            lines.append(f"     {tool.description}")
            if tool.parameters:
                params = ", ".join(f"{k}: {v}" for k, v in tool.parameters.items())
                lines.append(f"     Parametreler: {params}")
        return "\n".join(lines)
