"""No-code rol oluşturucu ve doğrulama testleri."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from mnacp.no_code.role_builder import RoleBuilder, RoleProposal, ToolSuggestion
from mnacp.no_code.validator import validate_proposal

# ------------------------------------------------------------------
# Validator testleri (Claude API gerektirmez)
# ------------------------------------------------------------------

def make_valid_proposal(**overrides) -> RoleProposal:
    defaults = dict(
        agent_name="FinanceAgent",
        agent_description="Finansal verileri analiz eden ve rapor üreten ajan",
        tags=["finance", "analysis"],
        tools=[
            ToolSuggestion(name="get_stock_price", description="Hisse senedi fiyatı getirir"),
            ToolSuggestion(name="calculate_roi", description="Yatırım getiri oranı hesaplar"),
        ],
        rationale="Finansal analiz için temel araçlar",
        user_description="Finans ajanı istiyorum",
    )
    defaults.update(overrides)
    return RoleProposal(**defaults)


def test_valid_proposal_passes():
    result = validate_proposal(make_valid_proposal())
    assert result.valid
    assert len(result.errors) == 0


def test_short_name_fails():
    result = validate_proposal(make_valid_proposal(agent_name="A"))
    assert not result.valid
    assert any("2 karakter" in e for e in result.errors)


def test_invalid_name_chars_fails():
    result = validate_proposal(make_valid_proposal(agent_name="My Agent!"))
    assert not result.valid


def test_no_tools_fails():
    result = validate_proposal(make_valid_proposal(tools=[]))
    assert not result.valid
    assert any("araç" in e for e in result.errors)


def test_duplicate_tool_names_fails():
    tools = [
        ToolSuggestion(name="same_tool", description="İlk araç"),
        ToolSuggestion(name="same_tool", description="İkinci araç"),
    ]
    result = validate_proposal(make_valid_proposal(tools=tools))
    assert not result.valid
    assert any("benzersiz" in e for e in result.errors)


def test_non_snake_case_tool_fails():
    tools = [ToolSuggestion(name="MyTool", description="Büyük harfli araç")]
    result = validate_proposal(make_valid_proposal(tools=tools))
    assert not result.valid
    assert any("snake_case" in e for e in result.errors)


def test_too_many_tools_gives_warning():
    tools = [
        ToolSuggestion(name=f"tool_{i}", description=f"Araç {i}")
        for i in range(11)
    ]
    result = validate_proposal(make_valid_proposal(tools=tools))
    assert result.valid  # hata değil, uyarı
    assert any("10'dan fazla" in w for w in result.warnings)


def test_short_description_fails():
    result = validate_proposal(make_valid_proposal(agent_description="kısa"))
    assert not result.valid


# ------------------------------------------------------------------
# RoleBuilder mock testi
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_role_builder_suggest_parses_json():
    builder = RoleBuilder.__new__(RoleBuilder)
    builder._model = "test"
    builder._registry_url = "http://localhost:8000"

    valid_json = json.dumps({
        "agent_name": "StockAgent",
        "agent_description": "Borsa verilerini analiz eden ajan",
        "tags": ["finance"],
        "tools": [
            {"name": "get_price", "description": "Fiyat getirir", "parameters": {"symbol": "string"}},
            {"name": "compute_avg", "description": "Ortalama hesaplar", "parameters": {}},
        ],
        "rationale": "Finans için temel araçlar",
    })

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=valid_json)]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    builder._client = mock_client

    proposal = await builder.suggest("Borsa analizi yapan bir ajan istiyorum")
    assert proposal.agent_name == "StockAgent"
    assert len(proposal.tools) == 2
    assert proposal.tools[0].name == "get_price"


def test_format_proposal():
    proposal = make_valid_proposal()
    text = RoleBuilder.format_proposal(proposal)
    assert "FinanceAgent" in text
    assert "get_stock_price" in text
    assert "calculate_roi" in text
