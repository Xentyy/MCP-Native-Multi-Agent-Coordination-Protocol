"""
Orkestratör Ajan — MNACP sisteminin beyni.

LangGraph state machine:
  START → decompose → assign → execute → aggregate → END
                        ↑_________↓ (tamamlanmamış görevler varsa döner)

Kullanıcıdan doğal dil görev alır, ayrıştırır, uygun ajanlara delege eder,
sonuçları Claude API ile birleştirir ve kullanıcıya sunar.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Awaitable, Callable
from uuid import UUID, uuid4

import anthropic
from langgraph.graph import END, StateGraph
from mnacp.agents.orchestrator.decomposer import DecompositionPlan, TaskDecomposer
from mnacp.agents.orchestrator.delegator import Delegator
from mnacp.protocol.schemas import DelegationResponse, DelegationStatus
from typing_extensions import TypedDict

EventCallback = Callable[[dict[str, Any]], Awaitable[None]]

logger = logging.getLogger(__name__)

AGGREGATE_SYSTEM = """Sen bir çok-ajanlı sistemin orkestratörüsün.
Birden fazla uzman ajanın ürettiği sonuçları kullanıcıya anlamlı, tutarlı ve özlü bir yanıt olarak birleştir.
Teknik detayları gizle; kullanıcı odaklı, net bir cevap ver."""


# ------------------------------------------------------------------
# LangGraph State
# ------------------------------------------------------------------

class OrchestratorState(TypedDict, total=False):
    task: str
    plan: DecompositionPlan | None
    completed_ids: set[str]
    failed_ids: set[str]
    results: dict[str, Any]          # subtask_id → sonuç
    errors: dict[str, str]           # subtask_id → hata mesajı
    final_answer: str
    chain: list[UUID]                 # delegasyon zinciri
    on_event: EventCallback | None   # canlı stream için


async def _emit(state: OrchestratorState, event: dict[str, Any]) -> None:
    cb = state.get("on_event")
    if cb is None:
        return
    try:
        await cb(event)
    except Exception:
        logger.exception("event callback hatası")


# ------------------------------------------------------------------
# Düğüm fonksiyonları
# ------------------------------------------------------------------

async def node_decompose(state: OrchestratorState, decomposer: TaskDecomposer) -> OrchestratorState:
    logger.info("Görev ayrıştırılıyor: %s", state["task"][:80])
    await _emit(state, {"type": "decompose_start", "task": state["task"]})
    plan = await decomposer.decompose(state["task"])
    logger.info("Plan: %d alt görev, paralel=%s", len(plan.subtasks), plan.can_parallelize)
    await _emit(state, {
        "type": "decompose_done",
        "can_parallelize": plan.can_parallelize,
        "subtasks": [
            {
                "id": s.id,
                "description": s.description,
                "required_capabilities": list(s.required_capabilities or []),
                "depends_on": list(s.depends_on or []),
            }
            for s in plan.subtasks
        ],
    })
    return {**state, "plan": plan}


async def node_assign_and_execute(
    state: OrchestratorState,
    delegator: Delegator,
) -> OrchestratorState:
    plan: DecompositionPlan = state["plan"]
    completed = set(state["completed_ids"])
    failed = set(state["failed_ids"])
    results = dict(state["results"])
    errors = dict(state["errors"])
    chain = list(state["chain"])

    ready = plan.ready_tasks(completed | failed)
    if not ready:
        return state

    context = {"previous_results": results, "original_task": state["task"]}

    async def run_one(subtask):
        # Önce adayı seç ki subtask_start event'inde agent_id paylaşılabilsin.
        candidate = await delegator.pick_candidate(subtask)
        agent_name = candidate.agent.name if candidate else None
        agent_id = str(candidate.agent.agent_id) if candidate else None
        subtask.assigned_agent_id = agent_id

        await _emit(state, {
            "type": "subtask_start",
            "subtask_id": subtask.id,
            "description": subtask.description,
            "agent_id": agent_id,
            "agent_name": agent_name,
        })

        if candidate is None:
            err = f"Uygun ajan bulunamadı: '{subtask.description[:60]}'"
            resp = DelegationResponse(request_id=uuid4(), status=DelegationStatus.FAILED, error=err)
            await _emit(state, {
                "type": "subtask_failed",
                "subtask_id": subtask.id,
                "agent_id": None,
                "error": err,
            })
            return resp

        try:
            resp = await delegator._delegation.delegate(
                from_agent_id=delegator._orchestrator_id,
                to_agent_id=candidate.agent.agent_id,
                to_agent_host=candidate.agent.host,
                to_agent_port=candidate.agent.port,
                task=subtask.description,
                context=context,
                chain=chain,
                to_agent_base_path=candidate.agent.base_path,
            )
        except Exception as exc:  # pragma: no cover — defensive
            await _emit(state, {
                "type": "subtask_failed",
                "subtask_id": subtask.id,
                "agent_id": agent_id,
                "error": str(exc),
            })
            raise

        if resp.status == DelegationStatus.COMPLETED:
            # Peer delegasyon bilgisini SSE'ye yayınla (ajan→ajan zinciri)
            if isinstance(resp.result, dict):
                for peer in resp.result.get("_peer_delegations", []):
                    if peer:
                        await _emit(state, {
                            "type": "peer_delegation",
                            "from_agent_id": peer.get("from_agent_id"),
                            "from_agent_name": peer.get("from_agent_name"),
                            "to_agent_id": peer.get("to_agent_id"),
                            "to_agent_name": peer.get("to_agent_name"),
                            "status": peer.get("status"),
                        })
            await _emit(state, {
                "type": "subtask_done",
                "subtask_id": subtask.id,
                "agent_id": agent_id,
                "agent_name": agent_name,
                "result_preview": json.dumps(resp.result, ensure_ascii=False, default=str)[:300],
            })
        else:
            await _emit(state, {
                "type": "subtask_failed",
                "subtask_id": subtask.id,
                "agent_id": agent_id,
                "error": resp.error or "bilinmeyen hata",
            })
        return resp

    if plan.can_parallelize:
        tasks = [run_one(subtask) for subtask in ready]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        pairs = list(zip(ready, responses))
    else:
        pairs = []
        for subtask in ready:
            try:
                resp = await run_one(subtask)
            except Exception as exc:
                resp = exc
            pairs.append((subtask, resp))

    for subtask, response in pairs:
        if isinstance(response, Exception):
            errors[subtask.id] = str(response)
            failed.add(subtask.id)
            subtask.error = str(response)
        elif response.status == DelegationStatus.COMPLETED:
            results[subtask.id] = response.result
            subtask.result = response.result
            completed.add(subtask.id)
        else:
            errors[subtask.id] = response.error or "Bilinmeyen hata"
            failed.add(subtask.id)
            subtask.error = errors[subtask.id]

    return {
        **state,
        "completed_ids": completed,
        "failed_ids": failed,
        "results": results,
        "errors": errors,
    }


async def node_aggregate(
    state: OrchestratorState,
    client: anthropic.Anthropic,
    model: str,
) -> OrchestratorState:
    plan: DecompositionPlan = state["plan"]

    summary_parts = []
    for subtask in plan.subtasks:
        if subtask.id in state["results"]:
            summary_parts.append(
                f"### {subtask.description}\nSonuç: {json.dumps(state['results'][subtask.id], ensure_ascii=False, default=str)[:500]}"
            )
        elif subtask.id in state["errors"]:
            summary_parts.append(f"### {subtask.description}\nHata: {state['errors'][subtask.id]}")

    if summary_parts:
        user_message = (
            f"Orijinal görev: {state['task']}\n\n"
            f"Alt görev sonuçları:\n" + "\n\n".join(summary_parts)
        )
    else:
        # Plan boştu ya da hiç alt görev üretilemedi — doğrudan cevapla.
        user_message = (
            f"Aşağıdaki görevi alt ajanlara delege etmeye gerek olmadan, "
            f"doğrudan kullanıcıya net ve kapsamlı bir cevap olarak yanıtla:\n\n"
            f"{state['task']}"
        )

    await _emit(state, {"type": "aggregate_start"})

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: client.messages.create(
            model=model,
            max_tokens=2048,
            system=AGGREGATE_SYSTEM,
            messages=[{"role": "user", "content": user_message}],
        ),
    )

    final = response.content[0].text
    await _emit(state, {"type": "final_answer", "answer": final})
    return {**state, "final_answer": final}


def should_continue(state: OrchestratorState) -> str:
    plan: DecompositionPlan = state["plan"]
    if plan is None:
        return "aggregate"
    all_ids = {s.id for s in plan.subtasks}
    done = state["completed_ids"] | state["failed_ids"]
    if all_ids <= done:
        return "aggregate"
    remaining = plan.ready_tasks(done)
    if not remaining:
        # Bağımlılık kilitlenmesi — tamamlanamayan görevler var
        return "aggregate"
    return "execute"


# ------------------------------------------------------------------
# OrchestratorAgent
# ------------------------------------------------------------------

class OrchestratorAgent:
    def __init__(
        self,
        registry_url: str = "http://localhost:8000",
        model: str = "claude-sonnet-4-5",
        max_delegation_depth: int = 5,
    ) -> None:
        self.agent_id = uuid4()
        self._model = model
        self._client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self._decomposer = TaskDecomposer(model=model, registry_url=registry_url)
        self._delegator = Delegator(
            orchestrator_id=self.agent_id,
            registry_url=registry_url,
            max_depth=max_delegation_depth,
        )
        self._graph = self._build_graph()

    def _build_graph(self) -> Any:
        decomposer = self._decomposer
        delegator = self._delegator
        client = self._client
        model = self._model

        builder = StateGraph(OrchestratorState)

        async def _decompose(s: OrchestratorState) -> OrchestratorState:
            return await node_decompose(s, decomposer)

        async def _execute(s: OrchestratorState) -> OrchestratorState:
            return await node_assign_and_execute(s, delegator)

        async def _aggregate(s: OrchestratorState) -> OrchestratorState:
            return await node_aggregate(s, client, model)

        builder.add_node("decompose", _decompose)
        builder.add_node("execute", _execute)
        builder.add_node("aggregate", _aggregate)

        builder.set_entry_point("decompose")
        builder.add_edge("decompose", "execute")
        builder.add_conditional_edges("execute", should_continue, {
            "execute": "execute",
            "aggregate": "aggregate",
        })
        builder.add_edge("aggregate", END)

        return builder.compile()

    async def run(self, task: str, on_event: EventCallback | None = None) -> str:
        """Görevi çalıştır ve nihai yanıtı döndür.

        on_event: opsiyonel async callback. Decompose/subtask/aggregate
        aşamalarında yapılandırılmış olay sözlükleri yayınlanır (SSE için).
        """
        initial_state: OrchestratorState = {
            "task": task,
            "plan": None,
            "completed_ids": set(),
            "failed_ids": set(),
            "results": {},
            "errors": {},
            "final_answer": "",
            "chain": [self.agent_id],
            "on_event": on_event,
        }

        final_state = await self._graph.ainvoke(initial_state)
        return final_state["final_answer"]

    def get_stats(self) -> dict[str, Any]:
        return self._delegator.get_stats()

    def get_delegation_history(self) -> list[dict[str, Any]]:
        return self._delegator.get_delegation_history()
