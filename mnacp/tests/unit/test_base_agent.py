"""BaseAgent ve araç katmanı unit testleri — registry'ye bağlanmadan."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from mnacp.agents.base_agent.agent import BaseAgent
from mnacp.mcp_servers.analysis_tools.tools import (
    CompareParams,
    GenerateReportParams,
    TrendAnalysisParams,
    compare,
    generate_report,
    trend_analysis,
)
from mnacp.mcp_servers.data_tools.tools import (
    CleanDataParams,
    ComputeStatisticsParams,
    FilterRowsParams,
    LoadCsvParams,
    clean_data,
    compute_statistics,
    filter_rows,
    load_csv,
)
from mnacp.protocol.schemas import (
    DelegationRequest,
    DelegationStatus,
    ToolSchema,
)

# ------------------------------------------------------------------
# Minimal somut ajan
# ------------------------------------------------------------------

class EchoAgent(BaseAgent):
    def define_tools(self) -> list[ToolSchema]:
        return [ToolSchema(name="echo", description="Girişi geri döndürür")]

    async def execute_tool(self, tool_name: str, parameters: dict[str, Any]) -> Any:
        if tool_name == "echo":
            return parameters.get("message", "")
        raise ValueError(f"Bilinmeyen araç: {tool_name}")


# ------------------------------------------------------------------
# Data tools testleri
# ------------------------------------------------------------------

def test_load_csv_basic():
    csv_text = "name,age\nAlice,30\nBob,25"
    rows = load_csv(LoadCsvParams(content=csv_text))
    assert len(rows) == 2
    assert rows[0]["name"] == "Alice"


def test_clean_data_removes_empty():
    rows = [{"a": "1", "b": ""}, {"a": "2", "b": "x"}]
    cleaned = clean_data(CleanDataParams(rows=rows, drop_empty=True))
    assert len(cleaned) == 1
    assert cleaned[0]["a"] == "2"


def test_compute_statistics():
    rows = [{"val": str(i)} for i in range(1, 6)]
    stats = compute_statistics(ComputeStatisticsParams(rows=rows, column="val"))
    assert stats["count"] == 5
    assert stats["mean"] == 3.0
    assert stats["min"] == 1.0
    assert stats["max"] == 5.0


def test_filter_rows_eq():
    rows = [{"city": "Istanbul"}, {"city": "Ankara"}, {"city": "Istanbul"}]
    result = filter_rows(FilterRowsParams(rows=rows, column="city", value="Istanbul", operator="eq"))
    assert len(result) == 2


def test_filter_rows_gt():
    rows = [{"score": "80"}, {"score": "50"}, {"score": "95"}]
    result = filter_rows(FilterRowsParams(rows=rows, column="score", value="70", operator="gt"))
    assert len(result) == 2


# ------------------------------------------------------------------
# Analysis tools testleri
# ------------------------------------------------------------------

def test_trend_analysis_up():
    result = trend_analysis(TrendAnalysisParams(values=[1.0, 2.0, 3.0, 4.0, 5.0]))
    assert result["trend"] == "up"
    assert result["slope"] > 0


def test_compare():
    result = compare(CompareParams(
        baseline={"accuracy": 0.80, "latency": 200.0},
        current={"accuracy": 0.90, "latency": 150.0},
    ))
    assert result["accuracy"]["direction"] == "up"
    assert result["latency"]["direction"] == "down"
    assert result["accuracy"]["change_pct"] > 0
    assert result["latency"]["delta"] < 0


def test_generate_report_markdown():
    report = generate_report(GenerateReportParams(
        title="Test Raporu",
        sections=[{"heading": "Özet", "content": "İyi gidiyor"}],
        format="markdown",
    ))
    assert "# Test Raporu" in report
    assert "## Özet" in report


# ------------------------------------------------------------------
# BaseAgent testleri (registry mock'lu)
# ------------------------------------------------------------------

@pytest.fixture
def echo_agent():
    return EchoAgent(name="Echo", description="Test ajanı", port=19000)


@pytest.mark.asyncio
async def test_agent_execute_tool(echo_agent):
    result = await echo_agent.execute_tool("echo", {"message": "merhaba"})
    assert result == "merhaba"


@pytest.mark.asyncio
async def test_delegation_depth_limit(echo_agent):
    chain = [uuid4() for _ in range(5)]
    req = DelegationRequest(
        from_agent_id=uuid4(),
        to_agent_id=echo_agent.agent_id,
        task="bir şey yap",
        delegation_chain=chain,
        max_depth=5,
    )
    response = await echo_agent.handle_delegation(req)
    assert response.status == DelegationStatus.REJECTED
    assert "derinliği" in response.error


@pytest.mark.asyncio
async def test_circular_delegation_rejected(echo_agent):
    req = DelegationRequest(
        from_agent_id=uuid4(),
        to_agent_id=echo_agent.agent_id,
        task="döngüsel görev",
        delegation_chain=[echo_agent.agent_id],  # kendi id'si zincirde
    )
    response = await echo_agent.handle_delegation(req)
    assert response.status == DelegationStatus.REJECTED
    assert "döngüsel" in response.error.lower()
