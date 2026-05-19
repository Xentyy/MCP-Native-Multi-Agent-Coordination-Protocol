"""Orkestratör bileşenleri unit testleri — dış bağımlılıklar mock'lu."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from mnacp.agents.orchestrator.decomposer import (
    DecompositionPlan,
    SubTask,
    TaskDecomposer,
)
from mnacp.agents.orchestrator.delegator import Delegator
from mnacp.protocol.schemas import DelegationResponse, DelegationStatus

# ------------------------------------------------------------------
# DecompositionPlan yardımcıları
# ------------------------------------------------------------------

def make_plan(n: int = 3, parallel: bool = False) -> DecompositionPlan:
    subtasks = [
        SubTask(
            id=f"t{i+1}",
            description=f"Alt görev {i+1}",
            required_capabilities=[f"cap{i+1}"],
            depends_on=[f"t{i}"] if i > 0 else [],
            parallel=parallel,
        )
        for i in range(n)
    ]
    return DecompositionPlan(
        subtasks=subtasks,
        execution_order=[s.id for s in subtasks],
        can_parallelize=parallel,
        original_task="test görevi",
    )


def test_ready_tasks_no_deps():
    plan = make_plan(1)
    ready = plan.ready_tasks(set())
    assert len(ready) == 1
    assert ready[0].id == "t1"


def test_ready_tasks_respects_deps():
    plan = make_plan(3)
    # t2 t1'e bağlı — t1 tamamlanmadan t2 hazır değil
    ready = plan.ready_tasks(set())
    assert len(ready) == 1
    assert ready[0].id == "t1"

    ready2 = plan.ready_tasks({"t1"})
    assert len(ready2) == 1
    assert ready2[0].id == "t2"


def test_ready_tasks_skips_assigned():
    plan = make_plan(2)
    plan.subtasks[0].assigned_agent_id = "some-agent"
    ready = plan.ready_tasks(set())
    assert len(ready) == 0  # t1 atanmış, t2 t1'e bağlı


def test_get_subtask():
    plan = make_plan(3)
    s = plan.get_subtask("t2")
    assert s is not None
    assert s.id == "t2"
    assert plan.get_subtask("t99") is None


# ------------------------------------------------------------------
# TaskDecomposer mock testi
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_decomposer_fallback_on_bad_json():
    decomposer = TaskDecomposer.__new__(TaskDecomposer)
    decomposer._model = "test"
    decomposer._registry_url = ""

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Bu JSON değil")]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    decomposer._client = mock_client

    plan = await decomposer.decompose("herhangi bir görev")
    assert len(plan.subtasks) == 1
    assert plan.subtasks[0].id == "t1"


@pytest.mark.asyncio
async def test_decomposer_parses_valid_json():
    import json
    decomposer = TaskDecomposer.__new__(TaskDecomposer)
    decomposer._model = "test"
    decomposer._registry_url = ""

    valid_json = json.dumps({
        "subtasks": [
            {"id": "t1", "description": "Veri yükle", "required_capabilities": ["load_csv"],
             "depends_on": [], "parallel": False},
            {"id": "t2", "description": "Analiz et", "required_capabilities": ["compute_statistics"],
             "depends_on": ["t1"], "parallel": False},
        ],
        "execution_order": ["t1", "t2"],
        "can_parallelize": False,
    })

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=valid_json)]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    decomposer._client = mock_client

    plan = await decomposer.decompose("CSV analiz et")
    assert len(plan.subtasks) == 2
    assert plan.subtasks[1].depends_on == ["t1"]


# ------------------------------------------------------------------
# Delegator mock testi
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delegator_returns_failed_when_no_agent():
    delegator = Delegator.__new__(Delegator)
    delegator._orchestrator_id = uuid4()

    mock_discovery = MagicMock()
    mock_discovery.find_agents = AsyncMock(return_value=[])
    delegator._discovery = mock_discovery

    mock_delegation = MagicMock()
    delegator._delegation = mock_delegation

    subtask = SubTask(id="t1", description="Görev", required_capabilities=["bilinmeyen_araç"])
    response = await delegator.execute_subtask(subtask, {}, [])

    assert response.status == DelegationStatus.FAILED
    assert "bulunamadı" in response.error


@pytest.mark.asyncio
async def test_delegator_delegates_when_agent_found():
    from mnacp.protocol.schemas import AgentInfo, AgentStatus, DiscoveryResult

    delegator = Delegator.__new__(Delegator)
    orch_id = uuid4()
    delegator._orchestrator_id = orch_id

    agent_id = uuid4()
    agent = AgentInfo(
        agent_id=agent_id, name="TestAgent", description="test",
        host="localhost", port=9001, tools=[], status=AgentStatus.ONLINE,
        trust_score=1.0, tags=[],
    )
    discovery_result = DiscoveryResult(agent=agent, similarity_score=0.9, matched_tools=[])

    mock_discovery = MagicMock()
    mock_discovery.find_agents = AsyncMock(return_value=[discovery_result])
    delegator._discovery = mock_discovery

    expected_response = DelegationResponse(
        request_id=uuid4(), status=DelegationStatus.COMPLETED, result={"ok": True}
    )
    mock_delegation = MagicMock()
    mock_delegation.delegate = AsyncMock(return_value=expected_response)
    delegator._delegation = mock_delegation

    subtask = SubTask(id="t1", description="CSV yükle", required_capabilities=["load_csv"])
    response = await delegator.execute_subtask(subtask, {}, [])

    assert response.status == DelegationStatus.COMPLETED
    assert subtask.assigned_agent_id == str(agent_id)
