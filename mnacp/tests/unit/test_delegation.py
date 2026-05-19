"""Delegasyon protokolü ve deadlock dedektörü testleri."""
from __future__ import annotations

from uuid import uuid4

import pytest
from mnacp.protocol.deadlock_detector import DeadlockDetector
from mnacp.protocol.delegation import DelegationManager
from mnacp.protocol.schemas import DelegationStatus

# ------------------------------------------------------------------
# DeadlockDetector testleri
# ------------------------------------------------------------------

def test_no_cycle_in_empty_chain():
    det = DeadlockDetector()
    b = uuid4()
    assert not det.has_cycle_in_chain([], b)


def test_cycle_detected_in_chain():
    det = DeadlockDetector()
    a, b = uuid4(), uuid4()
    chain = [a, b]
    assert det.has_cycle_in_chain(chain, a)  # A→B→A döngüsü


def test_no_global_cycle_linear():
    det = DeadlockDetector()
    a, b, c = uuid4(), uuid4(), uuid4()
    det.add_delegation(a, b)
    det.add_delegation(b, c)
    assert not det.has_global_cycle()


def test_global_cycle_detected():
    det = DeadlockDetector()
    a, b, c = uuid4(), uuid4(), uuid4()
    det.add_delegation(a, b)
    det.add_delegation(b, c)
    det.add_delegation(c, a)  # döngü kapat
    assert det.has_global_cycle()


def test_remove_delegation_breaks_cycle():
    det = DeadlockDetector()
    a, b = uuid4(), uuid4()
    det.add_delegation(a, b)
    det.add_delegation(b, a)
    assert det.has_global_cycle()
    det.remove_delegation(b, a)
    assert not det.has_global_cycle()


def test_deadlocked_agents_found():
    det = DeadlockDetector()
    a, b = uuid4(), uuid4()
    det.add_delegation(a, b)
    det.add_delegation(b, a)
    deadlocked = det.find_deadlocked_agents()
    assert len(deadlocked) >= 1
    group = deadlocked[0]
    assert str(a) in group and str(b) in group


def test_is_safe_to_delegate_blocks_chain_cycle():
    det = DeadlockDetector()
    a, b = uuid4(), uuid4()
    chain = [a, b]
    safe, reason = det.is_safe_to_delegate(b, a, chain)  # b→a ile A→B→A olur
    assert not safe
    assert "zincirde" in reason


def test_is_safe_to_delegate_blocks_global_cycle():
    det = DeadlockDetector()
    a, b, c = uuid4(), uuid4(), uuid4()
    det.add_delegation(a, b)
    det.add_delegation(b, c)
    safe, reason = det.is_safe_to_delegate(c, a, [])  # c→a ile A→B→C→A
    assert not safe


def test_is_safe_to_delegate_allows_valid():
    det = DeadlockDetector()
    a, b = uuid4(), uuid4()
    safe, reason = det.is_safe_to_delegate(a, b, [])
    assert safe
    assert reason == ""


# ------------------------------------------------------------------
# DelegationManager testleri (ağ bağlantısı olmadan)
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delegation_rejected_at_max_depth():
    manager = DelegationManager(max_depth=3)
    chain = [uuid4(), uuid4(), uuid4()]  # zaten 3 derin
    response = await manager.delegate(
        from_agent_id=uuid4(),
        to_agent_id=uuid4(),
        to_agent_host="localhost",
        to_agent_port=9999,
        task="test",
        chain=chain,
    )
    assert response.status == DelegationStatus.REJECTED
    assert "derinliği" in response.error


@pytest.mark.asyncio
async def test_delegation_rejected_on_cycle():
    manager = DelegationManager()
    a, b = uuid4(), uuid4()
    response = await manager.delegate(
        from_agent_id=b,
        to_agent_id=a,
        to_agent_host="localhost",
        to_agent_port=9999,
        task="test",
        chain=[a, b],  # zaten A→B, şimdi B→A dönmeye çalışıyor
    )
    assert response.status == DelegationStatus.REJECTED


@pytest.mark.asyncio
async def test_stats_after_rejection():
    manager = DelegationManager(max_depth=1)
    for _ in range(3):
        chain = [uuid4()]
        await manager.delegate(
            from_agent_id=uuid4(),
            to_agent_id=uuid4(),
            to_agent_host="localhost",
            to_agent_port=9999,
            task="test",
            chain=chain,
        )
    stats = manager.get_stats()
    assert stats["total"] == 3
    assert stats["rejected"] == 3
