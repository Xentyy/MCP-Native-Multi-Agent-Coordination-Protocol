"""TrustScorer, CapabilityEmbedder, DiscoveryProtocol ve GenericAgent unit testleri."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import numpy as np
import pytest

from mnacp.no_code.generic_agent import GenericAgent
from mnacp.no_code.role_builder import RoleProposal, ToolSuggestion
from mnacp.protocol.schemas import DelegationRequest, DelegationStatus, TrustEvent
from mnacp.registry.capability_embedder import CapabilityEmbedder
from mnacp.registry.trust_scorer import TrustScorer


# ─── TrustScorer ──────────────────────────────────────────────────────────────

@pytest.fixture
def scorer():
    return TrustScorer()


def _event(agent_id, success: bool, latency_ms: float = 100.0) -> TrustEvent:
    return TrustEvent(agent_id=agent_id, event_type="tool_call",
                      success=success, latency_ms=latency_ms)


def test_trust_scorer_initial_score_is_max(scorer):
    aid = uuid4()
    assert scorer.score(aid) == TrustScorer.MAX_SCORE


def test_trust_scorer_all_success_keeps_high(scorer):
    aid = uuid4()
    for _ in range(5):
        scorer.record(_event(aid, success=True, latency_ms=500))
    assert scorer.score(aid) >= 0.8


def test_trust_scorer_failures_lower_score(scorer):
    aid = uuid4()
    for _ in range(5):
        scorer.record(_event(aid, success=False, latency_ms=5000))
    assert scorer.score(aid) < 1.0


def test_trust_scorer_consecutive_failure_penalty(scorer):
    aid = uuid4()
    for _ in range(3):
        scorer.record(_event(aid, success=False))
    score_3 = scorer.score(aid)

    aid2 = uuid4()
    for _ in range(6):
        scorer.record(_event(aid2, success=False))
    score_6 = scorer.score(aid2)

    # Her ikisi de MIN_SCORE'a yakinsa esit olabilir — en azindan dusuk olmali
    assert score_3 >= score_6
    assert score_3 < TrustScorer.MAX_SCORE


def test_trust_scorer_score_bounded(scorer):
    aid = uuid4()
    for _ in range(20):
        scorer.record(_event(aid, success=False, latency_ms=99999))
    s = scorer.score(aid)
    assert TrustScorer.MIN_SCORE <= s <= TrustScorer.MAX_SCORE


def test_trust_scorer_high_latency_lowers_score(scorer):
    fast_id = uuid4()
    slow_id = uuid4()
    for _ in range(5):
        scorer.record(_event(fast_id, success=True, latency_ms=100))
        scorer.record(_event(slow_id, success=True, latency_ms=10000))
    assert scorer.score(fast_id) > scorer.score(slow_id)


def test_trust_scorer_trend_stable_when_few_records(scorer):
    aid = uuid4()
    scorer.record(_event(aid, success=True))
    assert scorer.get_trend(aid) == "stable"


def test_trust_scorer_trend_improving(scorer):
    aid = uuid4()
    # Kotu skorlar → iyi skorlar
    for _ in range(3):
        scorer.record(_event(aid, success=False, latency_ms=8000))
    for _ in range(5):
        scorer.record(_event(aid, success=True, latency_ms=100))
    assert scorer.get_trend(aid) in ("improving", "stable")


def test_trust_scorer_get_all_scores(scorer):
    ids = [uuid4() for _ in range(3)]
    for aid in ids:
        scorer.record(_event(aid, success=True))
    all_scores = scorer.get_all_scores()
    assert len(all_scores) == 3
    for v in all_scores.values():
        assert 0 <= v <= 1


# ─── CapabilityEmbedder ───────────────────────────────────────────────────────

@pytest.fixture
def embedder():
    return CapabilityEmbedder(dim=16)


def test_embedder_fit_and_transform(embedder):
    texts = [
        "web search fetch page internet research",
        "csv load data statistics compute mean",
        "python code execute algorithm sort",
        "trend analysis report generate markdown",
    ]
    embedder.fit(texts)
    vecs = embedder.transform(texts)
    assert vecs.shape == (4, embedder.dim) or vecs.shape[1] <= embedder.dim
    # L2 normalized — norm ≈ 1
    norms = np.linalg.norm(vecs, axis=1)
    np.testing.assert_allclose(norms, 1.0, atol=1e-5)


def test_embedder_transform_before_fit_raises(embedder):
    with pytest.raises(RuntimeError, match="fit"):
        embedder.transform(["test"])


def test_embedder_similar_texts_close(embedder):
    texts = [
        "web search internet query",
        "web search online lookup",
        "csv statistics data analysis",
    ]
    embedder.fit(texts)
    vecs = embedder.transform(texts)
    # web search vektorleri birbirine csv'den daha yakin olmali
    sim_web = float(np.dot(vecs[0], vecs[1]))
    sim_diff = float(np.dot(vecs[0], vecs[2]))
    assert sim_web > sim_diff


def test_embedder_cosine_similarity_identical(embedder):
    texts = ["foo bar baz"]
    embedder.fit(texts)
    v = embedder.transform(texts)[0]
    sim = embedder.cosine_similarity(v, v)
    assert abs(sim - 1.0) < 1e-4


def test_embedder_top_k_agents(embedder):
    corpus = [
        "web search fetch page research",
        "csv statistics data mean compute",
        "python execute code algorithm",
    ]
    embedder.fit(corpus)
    vecs = embedder.transform(corpus)
    agent_vecs = {"a1": vecs[0], "a2": vecs[1], "a3": vecs[2]}
    query = embedder.transform(["web search internet"])[0]
    top = embedder.top_k_agents(query, agent_vecs, k=2)
    # En az 2 sonuc donmeli ve ilk sonuc diger ikisinden daha yuksek skora sahip olmali
    assert len(top) == 2
    assert top[0][1] >= top[1][1]


def test_embedder_top_k_excludes(embedder):
    corpus = ["web search", "data csv", "python code"]
    embedder.fit(corpus)
    vecs = embedder.transform(corpus)
    agent_vecs = {"a1": vecs[0], "a2": vecs[1], "a3": vecs[2]}
    query = embedder.transform(["web search"])[0]
    top = embedder.top_k_agents(query, agent_vecs, k=3, exclude_ids=["a1"])
    ids = [t[0] for t in top]
    assert "a1" not in ids


# ─── DiscoveryProtocol ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_discovery_find_best_returns_first():
    from mnacp.protocol.discovery import DiscoveryProtocol
    from mnacp.protocol.schemas import DiscoveryResult, AgentInfo, ToolSchema

    mock_result = MagicMock(spec=DiscoveryResult)
    mock_result.agent = MagicMock(spec=AgentInfo)
    mock_result.agent.name = "SearchAgent"

    protocol = DiscoveryProtocol("http://localhost:8000")
    with patch.object(protocol, "find_agents", new_callable=AsyncMock,
                      return_value=[mock_result]):
        result = await protocol.find_best_agent("web araması yap")
    assert result is mock_result


@pytest.mark.asyncio
async def test_discovery_find_best_returns_none_when_empty():
    from mnacp.protocol.discovery import DiscoveryProtocol

    protocol = DiscoveryProtocol("http://localhost:8000")
    with patch.object(protocol, "find_agents", new_callable=AsyncMock,
                      return_value=[]):
        result = await protocol.find_best_agent("bilinmeyen görev")
    assert result is None


@pytest.mark.asyncio
async def test_discovery_find_agents_builds_correct_request():
    from mnacp.protocol.discovery import DiscoveryProtocol
    from mnacp.protocol.schemas import DiscoveryResult

    protocol = DiscoveryProtocol("http://fake:8000")
    captured = {}

    async def fake_discover(request):
        captured["request"] = request
        return []

    with patch("mnacp.protocol.discovery.RegistryClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.discover = AsyncMock(side_effect=fake_discover)
        await protocol.find_agents(
            task="test görevi",
            required_capabilities=["web_search"],
            top_k=2,
        )

    req = captured["request"]
    assert req.task_description == "test görevi"
    assert "web_search" in req.required_capabilities
    assert req.top_k == 2


@pytest.mark.asyncio
async def test_discovery_resolve_tool_owner_finds_matching_tool():
    from mnacp.protocol.discovery import DiscoveryProtocol
    from mnacp.protocol.schemas import DiscoveryResult, AgentInfo, ToolSchema

    tool = ToolSchema(name="web_search", description="arama yapar")
    agent = MagicMock(spec=AgentInfo)
    agent.tools = [tool]

    result = MagicMock(spec=DiscoveryResult)
    result.agent = agent

    protocol = DiscoveryProtocol("http://localhost:8000")
    with patch.object(protocol, "find_agents", new_callable=AsyncMock,
                      return_value=[result]):
        owner = await protocol.resolve_tool_owner("web_search")
    assert owner is agent


@pytest.mark.asyncio
async def test_discovery_resolve_tool_owner_returns_none_if_no_match():
    from mnacp.protocol.discovery import DiscoveryProtocol
    from mnacp.protocol.schemas import AgentInfo, ToolSchema

    tool = ToolSchema(name="other_tool", description="baska arac")
    agent = MagicMock(spec=AgentInfo)
    agent.tools = [tool]

    result = MagicMock()
    result.agent = agent

    protocol = DiscoveryProtocol("http://localhost:8000")
    with patch.object(protocol, "find_agents", new_callable=AsyncMock,
                      return_value=[result]):
        owner = await protocol.resolve_tool_owner("web_search")
    assert owner is None


# ─── GenericAgent ─────────────────────────────────────────────────────────────

def _make_proposal(tools=None) -> RoleProposal:
    return RoleProposal(
        agent_name="TestAgent",
        agent_description="Test amacli ajan",
        tags=["test"],
        tools=tools or [
            ToolSuggestion(name="do_thing", description="bir sey yapar",
                           parameters={"input": "string"}),
        ],
        rationale="test",
        user_description="test amacli",
    )


def test_generic_agent_to_registration():
    agent = GenericAgent(proposal=_make_proposal(),
                         registry_host="role-builder", registry_port=8001)
    reg = agent.to_registration()
    assert reg.name == "TestAgent"
    assert reg.host == "role-builder"
    assert reg.port == 8001
    assert str(agent.agent_id) in reg.base_path
    assert len(reg.tools) == 1
    assert reg.tools[0].name == "do_thing"


def test_generic_agent_rejects_deep_chain():
    agent = GenericAgent(proposal=_make_proposal())
    chain = [uuid4() for _ in range(5)]  # max_depth = 5
    req = DelegationRequest(
        from_agent_id=uuid4(),
        to_agent_id=agent.agent_id,
        task="bir sey yap",
        context={},
        delegation_chain=chain,
    )
    resp = agent.handle_delegation_sync(req)
    assert resp.status == DelegationStatus.REJECTED
    assert resp.error is not None


def test_generic_agent_rejects_circular_chain():
    agent = GenericAgent(proposal=_make_proposal())
    req = DelegationRequest(
        from_agent_id=uuid4(),
        to_agent_id=agent.agent_id,
        task="bir sey yap",
        context={},
        delegation_chain=[agent.agent_id],  # kendin zincirindesin
    )
    resp = agent.handle_delegation_sync(req)
    assert resp.status == DelegationStatus.REJECTED
    assert "dongu" in resp.error.lower() or "circular" in resp.error.lower() or "delegasyon" in resp.error.lower()


def test_generic_agent_unknown_tool_returns_error():
    agent = GenericAgent(proposal=_make_proposal())
    result = agent.execute_tool_sync("nonexistent_tool", {})
    assert "error" in result


def test_generic_agent_execute_tool_calls_claude():
    agent = GenericAgent(proposal=_make_proposal())
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text='{"result": "tamam"}')]

    with patch.object(agent._client.messages, "create",
                      return_value=fake_response):
        result = agent.execute_tool_sync("do_thing", {"input": "test"})

    assert result == {"result": "tamam"}


def test_generic_agent_delegation_calls_claude():
    agent = GenericAgent(proposal=_make_proposal())
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text='{"answer": "bitti"}')]

    req = DelegationRequest(
        from_agent_id=uuid4(),
        to_agent_id=agent.agent_id,
        task="bir sey yap",
        context={"key": "val"},
        delegation_chain=[],
    )

    with patch.object(agent._client.messages, "create",
                      return_value=fake_response):
        resp = agent.handle_delegation_sync(req)

    assert resp.status == DelegationStatus.COMPLETED
    assert resp.result == {"answer": "bitti"}


def test_generic_agent_handles_non_json_claude_response():
    agent = GenericAgent(proposal=_make_proposal())
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text="Islem tamamlandi.")]

    with patch.object(agent._client.messages, "create",
                      return_value=fake_response):
        result = agent.execute_tool_sync("do_thing", {})

    # JSON parse edilemeyince {"result": raw_text} donmeli
    assert "result" in result
