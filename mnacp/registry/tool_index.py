from __future__ import annotations

from uuid import UUID

from mnacp.protocol.schemas import ToolSchema


class ToolIndex:
    """
    Araç adı → ajan ID eşlemesi.
    Bir araç birden fazla ajanda olabilir; tüm sahipler döndürülür.
    """

    def __init__(self) -> None:
        self._tool_to_agents: dict[str, set[str]] = {}
        self._agent_to_tools: dict[str, list[ToolSchema]] = {}

    def register(self, agent_id: UUID, tools: list[ToolSchema]) -> None:
        aid = str(agent_id)
        self._agent_to_tools[aid] = tools
        for tool in tools:
            self._tool_to_agents.setdefault(tool.name, set()).add(aid)

    def unregister(self, agent_id: UUID) -> None:
        aid = str(agent_id)
        tools = self._agent_to_tools.pop(aid, [])
        for tool in tools:
            self._tool_to_agents.get(tool.name, set()).discard(aid)

    def agents_for_tool(self, tool_name: str) -> list[str]:
        return list(self._tool_to_agents.get(tool_name, set()))

    def tools_for_agent(self, agent_id: UUID) -> list[ToolSchema]:
        return self._agent_to_tools.get(str(agent_id), [])

    def all_tool_names(self) -> list[str]:
        return list(self._tool_to_agents.keys())

    def find_tools_matching(self, keyword: str) -> list[tuple[str, list[str]]]:
        kw = keyword.lower()
        results = []
        for tool_name, agents in self._tool_to_agents.items():
            if kw in tool_name.lower():
                results.append((tool_name, list(agents)))
        return results
