from __future__ import annotations

import json
import os
from pathlib import Path

_STORE_PATH = Path(os.environ.get("AGENTS_STORE_PATH", Path(__file__).parent / "agents_store.json"))


def _read() -> list[dict]:
    if not _STORE_PATH.exists():
        return []
    try:
        return json.loads(_STORE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def _write(records: list[dict]) -> None:
    _STORE_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def load_agents() -> list[dict]:
    return _read()


def save_agent(record: dict) -> None:
    records = _read()
    for i, r in enumerate(records):
        if r.get("agent_id") == record.get("agent_id"):
            records[i] = record
            _write(records)
            return
    records.append(record)
    _write(records)


def remove_agent(agent_id: str) -> None:
    records = [r for r in _read() if r.get("agent_id") != agent_id]
    _write(records)
