from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"


class ToolSchema(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class AgentRegistration(BaseModel):
    agent_id: UUID = Field(default_factory=uuid4)
    name: str
    description: str
    host: str
    port: int
    tools: list[ToolSchema]
    status: AgentStatus = AgentStatus.ONLINE
    registered_at: datetime = Field(default_factory=datetime.utcnow)
    trust_score: float = Field(default=1.0, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    base_path: str = Field(default="")
    api_key: str = Field(default="")  # Registry doğrulaması için; boş → key kontrolü devre dışı


class AgentInfo(BaseModel):
    agent_id: UUID
    name: str
    description: str
    host: str
    port: int
    tools: list[ToolSchema]
    status: AgentStatus
    trust_score: float
    tags: list[str]
    base_path: str = Field(default="")


class DiscoveryRequest(BaseModel):
    task_description: str
    required_capabilities: list[str] = Field(default_factory=list)
    top_k: int = Field(default=3, ge=1, le=10)
    exclude_agent_ids: list[UUID] = Field(default_factory=list)


class DiscoveryResult(BaseModel):
    agent: AgentInfo
    similarity_score: float
    matched_tools: list[str]


class DelegationRequest(BaseModel):
    request_id: UUID = Field(default_factory=uuid4)
    from_agent_id: UUID
    to_agent_id: UUID
    task: str
    context: dict[str, Any] = Field(default_factory=dict)
    delegation_chain: list[UUID] = Field(default_factory=list)
    max_depth: int = Field(default=5)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DelegationStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class DelegationResponse(BaseModel):
    request_id: UUID
    status: DelegationStatus
    result: Any = None
    error: str | None = None
    delegated_to: UUID | None = None
    completed_at: datetime | None = None


class TrustEvent(BaseModel):
    agent_id: UUID
    event_type: str
    success: bool
    latency_ms: float | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
