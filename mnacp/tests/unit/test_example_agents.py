"""Örnek ajanların araç çağrısı ve delegasyon işleme testleri."""
from __future__ import annotations

import pytest
from mnacp.agents.example_agents.analysis_agent.agent import AnalysisAgent
from mnacp.agents.example_agents.code_agent.agent import CodeAgent
from mnacp.agents.example_agents.data_agent.agent import DataAgent
from mnacp.agents.example_agents.search_agent.agent import SearchAgent

# ------------------------------------------------------------------
# DataAgent
# ------------------------------------------------------------------

@pytest.fixture
def data_agent():
    return DataAgent()


def test_data_agent_defines_tools(data_agent):
    tools = data_agent.define_tools()
    names = {t.name for t in tools}
    assert {"load_csv", "clean_data", "compute_statistics", "filter_rows"} <= names


@pytest.mark.asyncio
async def test_data_agent_load_csv(data_agent):
    result = await data_agent.execute_tool("load_csv", {
        "content": "name,score\nAlice,90\nBob,75"
    })
    assert len(result) == 2
    assert result[0]["name"] == "Alice"


@pytest.mark.asyncio
async def test_data_agent_compute_stats(data_agent):
    rows = [{"val": str(i)} for i in range(1, 6)]
    result = await data_agent.execute_tool("compute_statistics", {
        "rows": rows, "column": "val"
    })
    assert result["mean"] == 3.0
    assert result["count"] == 5


@pytest.mark.asyncio
async def test_data_agent_delegated_task_statistics(data_agent):
    rows = [{"price": str(i * 10)} for i in range(1, 4)]
    result = await data_agent._process_delegated_task(
        "istatistik hesapla", {"rows": rows, "column": "price"}
    )
    assert "mean" in result


@pytest.mark.asyncio
async def test_data_agent_unknown_tool_raises(data_agent):
    with pytest.raises(ValueError, match="bilinmeyen araç"):
        await data_agent.execute_tool("nonexistent", {})


# ------------------------------------------------------------------
# SearchAgent
# ------------------------------------------------------------------

@pytest.fixture
def search_agent():
    return SearchAgent()


def test_search_agent_defines_tools(search_agent):
    tools = search_agent.define_tools()
    names = {t.name for t in tools}
    assert {"web_search", "fetch_page", "summarize", "extract_links"} <= names


@pytest.mark.asyncio
async def test_search_agent_web_search(search_agent):
    result = await search_agent.execute_tool("web_search", {
        "query": "Python MCP protocol", "max_results": 3
    })
    assert isinstance(result, list)
    assert len(result) >= 1
    assert "title" in result[0]


@pytest.mark.asyncio
async def test_search_agent_summarize(search_agent):
    text = "Bu bir test metnidir. İkinci cümle. Üçüncü cümle. Dördüncü cümle."
    result = await search_agent.execute_tool("summarize", {
        "text": text, "max_sentences": 2
    })
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_search_agent_delegated_task(search_agent):
    result = await search_agent._process_delegated_task(
        "ara: Python çok-ajanlı sistemler", {"query": "Python multi-agent"}
    )
    assert "search_results" in result or isinstance(result, list)


# ------------------------------------------------------------------
# AnalysisAgent
# ------------------------------------------------------------------

@pytest.fixture
def analysis_agent():
    return AnalysisAgent()


def test_analysis_agent_defines_tools(analysis_agent):
    tools = analysis_agent.define_tools()
    names = {t.name for t in tools}
    assert {"trend_analysis", "compare", "generate_report", "correlation"} <= names


@pytest.mark.asyncio
async def test_analysis_agent_trend(analysis_agent):
    result = await analysis_agent.execute_tool("trend_analysis", {
        "values": [1.0, 2.0, 3.0, 4.0, 5.0], "window": 2
    })
    assert result["trend"] == "up"
    assert "slope" in result


@pytest.mark.asyncio
async def test_analysis_agent_generate_report(analysis_agent):
    result = await analysis_agent.execute_tool("generate_report", {
        "title": "Test Raporu",
        "sections": [{"heading": "Özet", "content": "Her şey yolunda"}],
        "format": "markdown",
    })
    assert "# Test Raporu" in result


@pytest.mark.asyncio
async def test_analysis_agent_correlation(analysis_agent):
    result = await analysis_agent.execute_tool("correlation", {
        "x": [1.0, 2.0, 3.0, 4.0],
        "y": [2.0, 4.0, 6.0, 8.0],
    })
    assert abs(result["pearson_r"] - 1.0) < 0.001


@pytest.mark.asyncio
async def test_analysis_agent_delegated_report(analysis_agent):
    result = await analysis_agent._process_delegated_task(
        "rapor oluştur",
        {"title": "Özet", "previous_results": {"t1": {"mean": 3.5}}}
    )
    assert isinstance(result, str)
    assert "Özet" in result or "t1" in result


# ------------------------------------------------------------------
# CodeAgent
# ------------------------------------------------------------------

@pytest.fixture
def code_agent():
    return CodeAgent()


def test_code_agent_defines_tools(code_agent):
    tools = code_agent.define_tools()
    names = {t.name for t in tools}
    assert {"execute_python", "analyze_code", "format_code", "extract_functions"} <= names


@pytest.mark.asyncio
async def test_code_agent_execute_python(code_agent):
    result = await code_agent.execute_tool("execute_python", {
        "code": "print(2 + 2)", "timeout": 5
    })
    assert result["success"] is True
    assert "4" in result["stdout"]


@pytest.mark.asyncio
async def test_code_agent_analyze_code(code_agent):
    code = "def hello(name):\n    return f'Hello {name}'\n"
    result = await code_agent.execute_tool("analyze_code", {"code": code})
    assert result["functions"][0]["name"] == "hello"
    assert result["lines"] >= 2


@pytest.mark.asyncio
async def test_code_agent_blocks_banned_import(code_agent):
    result = await code_agent.execute_tool("execute_python", {
        "code": "import os\nprint(os.getcwd())", "timeout": 5
    })
    assert result["success"] is False
    assert "Güvenlik" in result.get("error", "")


@pytest.mark.asyncio
async def test_code_agent_fibonacci_template(code_agent):
    result = await code_agent._process_delegated_task(
        "Fibonacci dizisinin 10. terimini hesapla", {}
    )
    assert result.get("success") is True
    assert "55" in result.get("stdout", "")


@pytest.mark.asyncio
async def test_code_agent_bubble_sort_template(code_agent):
    result = await code_agent._process_delegated_task(
        "Python'da bubble sort algoritması yaz ve çalıştır", {}
    )
    assert result.get("success") is True
    assert "Sorted" in result.get("stdout", "")
