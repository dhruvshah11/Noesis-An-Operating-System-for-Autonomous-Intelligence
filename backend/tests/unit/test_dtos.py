"""
Tests for new persistence DTOs in astra.types (M1.1).

Every new DTO defined in ``astra/types.py`` (User / Message / Memory /
Document / KnowledgeObject / Artifact / TaskExecution) must:
  * construct with zero-arg defaults where allowed
  * round-trip JSON via model_dump -> model_construct without loss
  * reject extras via extra="forbid"
  * enforce schema ranges (importance 0..1, positive byte sizes, etc.)
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from noesis.types import (
    Artifact,
    Document,
    KnowledgeObject,
    Memory,
    Message,
    TaskExecution,
    User,
)

# ---------------------------------------------------------------------------
# User DTO
# ---------------------------------------------------------------------------


def test_user_defaults_and_validation():
    u = User(email="admin@astraos.test")
    assert u.email == "admin@astraos.test"
    assert u.is_active is True
    assert u.is_admin is False
    assert isinstance(u.id, UUID)
    # extra="forbid" should reject unknown fields
    with pytest.raises(ValidationError):  # pydantic v2 ValidationError
        User(email="a@b.c", not_a_field=True)


def test_user_json_round_trip():
    u = User(email="sre@astraos.test", full_name="SRE Bot", is_admin=True)
    raw = u.model_dump(mode="json")
    restored = User.model_validate(raw)
    assert restored.id == u.id
    assert restored.email == u.email
    assert restored.is_admin is True
    assert isinstance(restored.created_at, datetime)


# ---------------------------------------------------------------------------
# Message DTO
# ---------------------------------------------------------------------------


def test_message_enforces_conversation_id():
    with pytest.raises(ValidationError):
        Message.model_validate({"role": "user", "content": "hi"})


def test_message_round_trip_preserves_tool_calls():
    conv_id = uuid4()
    m = Message(
        conversation_id=conv_id,
        role="assistant",
        tool_calls=[{"id": "call_1", "type": "function", "function": {"name": "a", "arguments": "{}"}}],
        prompt_tokens=12,
        completion_tokens=34,
    )
    restored = Message.model_validate(m.model_dump(mode="json"))
    assert restored.conversation_id == conv_id
    assert restored.tool_calls[0]["function"]["name"] == "a"  # type: ignore[index]
    assert restored.completion_tokens == 34


# ---------------------------------------------------------------------------
# Memory DTO
# ---------------------------------------------------------------------------


def test_memory_importance_bounds():
    valid = Memory(
        vector_id=uuid4(),
        memory_type="semantic",
        content="important thing",
        importance=0.5,
    )
    assert valid.importance == 0.5
    with pytest.raises(ValidationError):
        Memory(
            vector_id=uuid4(),
            memory_type="x",
            content="bad",
            importance=2.0,  # out of range
        )


def test_memory_scope_literals():
    m = Memory(vector_id=uuid4(), memory_type="episodic", content="hi", scope="project", scope_id="proj-1")
    assert m.scope == "project"
    with pytest.raises(ValidationError):
        Memory.model_validate(
            {
                "vector_id": str(uuid4()),
                "memory_type": "semantic",
                "content": "x",
                "scope": "nonsense",  # invalid literal
                "vector_id_bogus": None,
            }
        )


# ---------------------------------------------------------------------------
# Document DTO
# ---------------------------------------------------------------------------


def test_document_defaults():
    d = Document(title="Spec v1", source_uri="file:///tmp/spec.pdf")
    assert d.ingestion_status == "pending"
    assert d.mime_type == "application/octet-stream"


def test_document_ingestion_literals():
    for valid in ("pending", "processing", "ready", "failed"):
        Document(title="T", source_uri="file:///tmp/x", ingestion_status=valid)
    with pytest.raises(ValidationError):
        Document(title="T", source_uri="s3://x", ingestion_status="corrupt")


# ---------------------------------------------------------------------------
# KnowledgeObject DTO
# ---------------------------------------------------------------------------


def test_knowledge_object_versioning_and_tags():
    k = KnowledgeObject(
        workspace_id=str(uuid4()),
        kind="decision",
        title="Use Postgres over MySQL",
        version=3,
        tags=["infra", "storage", "adr"],
        references=["https://wiki/adr/013"],
    )
    assert k.version == 3
    assert "infra" in k.tags
    assert k.parent_id is None


def test_knowledge_object_round_trip():
    k = KnowledgeObject(kind="report", title="R", body="<body/>", metadata={"pages": 3})
    restored = KnowledgeObject.model_validate(k.model_dump(mode="json"))
    assert restored.metadata["pages"] == 3
    assert restored.body == "<body/>"


# ---------------------------------------------------------------------------
# Artifact DTO
# ---------------------------------------------------------------------------


def test_artifact_sha_and_size_bytes():
    a = Artifact(
        kind="image/png",
        name="chart.png",
        mime_type="image/png",
        size_bytes=1024,
        sha256="0" * 64,
    )
    assert a.size_bytes == 1024
    assert len(a.sha256) == 64  # type: ignore[arg-type]


def test_artifact_required_fields():
    # `kind` and `name` are required; id is auto-uuid
    with pytest.raises(ValidationError):
        Artifact.model_validate({"size_bytes": 0})


# ---------------------------------------------------------------------------
# TaskExecution DTO
# ---------------------------------------------------------------------------


def test_task_execution_defaults():
    te = TaskExecution(agent_type="planner", description="plan a project")
    assert te.status == 0
    assert te.cost_usd == 0.0
    assert te.duration_ms == 0.0


def test_task_execution_foreign_ids_optional():
    te = TaskExecution(
        conversation_id=str(uuid4()),
        run_id=str(uuid4()),
        agent_type="tool",
        description="x",
        status=3,
    )
    data = te.model_dump(mode="json")
    restored = TaskExecution.model_validate(data)
    assert restored.run_id == te.run_id
    assert restored.status == 3
