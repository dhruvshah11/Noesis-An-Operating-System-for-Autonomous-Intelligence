"""
Unit tests for :mod:`astra.types`.

We validate:
  * ChatMessage invariants (content-or-tool_calls-or-tool-role)
  * ExecutionPlan contiguous-index validator
  * TokenUsage addition
  * Enum (de)serialisation via Pydantic v2 ``use_enum_values``
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from noesis.types import (
    AgentType,
    APIEnvelope,
    ChatMessage,
    ExecutionPlan,
    MessageRole,
    PlanStep,
    ProviderResponse,
    ProviderType,
    TaskStatus,
    TokenUsage,
)

# -------- ChatMessage ----------------------------------------------------


def test_chat_message_defaults() -> None:
    m = ChatMessage(role=MessageRole.USER, content="hi")
    assert m.id is not None
    assert m.timestamp is not None
    assert m.role == "user"  # use_enum_values → serialised to str
    assert m.content == "hi"


def test_chat_message_requires_content_xor_tool_calls() -> None:
    # Assistant message with no content AND no tool_calls → invalid.
    with pytest.raises(ValidationError):
        ChatMessage(role=MessageRole.ASSISTANT)
    # User message with empty string content → OK (empty is different from None).
    m = ChatMessage(role=MessageRole.USER, content="")
    assert m.content == ""


def test_chat_message_tool_role_requires_tool_call_id() -> None:
    with pytest.raises(ValidationError, match="tool_call_id"):
        ChatMessage(role=MessageRole.TOOL, content="ok")


def test_chat_message_tool_role_ok() -> None:
    m = ChatMessage(role=MessageRole.TOOL, tool_call_id="call_1", content="ok")
    assert m.tool_call_id == "call_1"
    assert m.role == MessageRole.TOOL


def test_chat_message_assistant_with_tool_calls_can_omit_content() -> None:
    """An assistant message requesting tool calls may omit text content."""
    m = ChatMessage(
        role=MessageRole.ASSISTANT,
        tool_calls=[{"id": "tc_1", "type": "function", "function": {"name": "calc", "arguments": {"a": 1}}}],
    )
    assert m.content is None
    assert len(m.tool_calls or []) == 1


def test_chat_message_use_enum_values_roundtrip() -> None:
    m = ChatMessage(role=MessageRole.SYSTEM, content="sys")
    raw = m.model_dump_json()
    parsed = json.loads(raw)
    assert parsed["role"] == "system"
    restored = ChatMessage.model_validate_json(raw)
    assert restored.role == MessageRole.SYSTEM


# -------- ExecutionPlan + PlanStep --------------------------------------


def test_plan_step_defaults() -> None:
    s = PlanStep(index=0, description="Do A", assigned_agent=AgentType.PLANNER)
    assert s.status is TaskStatus.PENDING
    assert s.confidence == pytest.approx(0.0)


def test_plan_step_description_min_length() -> None:
    with pytest.raises(ValidationError, match=r"string_too_short|minimum length"):
        PlanStep(index=0, description="Hi", assigned_agent=AgentType.PLANNER)


def test_execution_plan_indices_must_be_contiguous() -> None:
    with pytest.raises(ValidationError, match="contiguous"):
        ExecutionPlan(
            goal="do X correctly",
            reasoning="because it matters",
            steps=[
                PlanStep(index=0, description="Plan the work", assigned_agent=AgentType.PLANNER),
                PlanStep(index=2, description="Write the code", assigned_agent=AgentType.CODING),
            ],
        )


def test_execution_plan_valid_contiguous() -> None:
    plan = ExecutionPlan(
        goal="do X correctly",
        reasoning="because it matters",
        steps=[
            PlanStep(index=0, description="Plan the work", assigned_agent=AgentType.PLANNER),
            PlanStep(index=1, description="Write the code", assigned_agent=AgentType.CODING),
        ],
    )
    assert len(plan.steps) == 2
    assert plan.steps[0].assigned_agent == AgentType.PLANNER
    assert plan.steps[1].assigned_agent == AgentType.CODING


# -------- TokenUsage + ProviderResponse ---------------------------------


def test_token_usage_addition() -> None:
    a = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    b = TokenUsage(prompt_tokens=3, completion_tokens=2, total_tokens=5)
    c = a + b
    assert c.prompt_tokens == 13
    assert c.completion_tokens == 7
    assert c.total_tokens == 20


def test_token_usage_addition_zero_identity() -> None:
    a = TokenUsage(prompt_tokens=7, completion_tokens=3, total_tokens=10)
    zero = TokenUsage()
    assert (a + zero).total_tokens == 10


def test_provider_response_defaults() -> None:
    r = ProviderResponse(provider=ProviderType.OPENAI, model="x", content="ok")
    assert r.usage.total_tokens == 0
    assert r.finish_reason == "unknown"


# -------- APIEnvelope ----------------------------------------------------


def test_envelope_ok_shape() -> None:
    env = APIEnvelope[str](ok=True, data="hello", request_id="r1")
    assert env.model_dump(mode="json") == {
        "ok": True,
        "data": "hello",
        "error": None,
        "request_id": "r1",
        "meta": {},
    }


def test_envelope_err_shape() -> None:
    env = APIEnvelope(ok=False, error="boom")
    assert env.ok is False
    assert env.data is None
    assert env.error == "boom"
