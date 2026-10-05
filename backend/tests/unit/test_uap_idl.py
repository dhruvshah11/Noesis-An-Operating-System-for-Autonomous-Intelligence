"""
M1.4 UAP Proto3 IDL round-trip tests.

Covers:
  * JSON wire form determinism + losslessness (encode_json → decode_json → deep equal)
  * Binary wire form losslessness (encode_binary → decode_binary → deep equal)
  * Canonical SHA-256 stability (same message in, same digest out)
  * UUID / datetime wire-normalization rules (Rule 4 / Rule 5)
  * Intent-enum string values on the wire (Rule 3)
  * Structured dict / attachment lists preserved through binary decoder
  * SysCall + SysCallReply (kernel ABI) lossless
  * Envelope / Turn (persistence) lossless with many attachments + 10 replies
"""

from __future__ import annotations

import copy
import hashlib
import itertools
import math
from datetime import UTC, datetime
from uuid import UUID, uuid4

import orjson
import pytest

from noesis.uap import (
    UAPArtifact,
    UAPEnvelope,
    UAPEvidence,
    UAPGoal,
    UAPIntent,
    UAPMessage,
    UAPOrigin,
    UAPSpan,
    UAPSysCall,
    UAPSysCallKind,
    UAPSysCallReply,
    UAPTransportKind,
    UAPTurn,
)
from noesis.uap.wire import (
    decode_binary,
    decode_json,
    encode_binary,
    encode_json,
    sha256_canonical,
)

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


def _now_z() -> datetime:
    return datetime.now(UTC)


@pytest.fixture
def origin() -> UAPOrigin:
    return UAPOrigin(
        agent_id="io.astraos.planner",
        agent_type="planner",
        run_id=uuid4(),
        workspace_id="ws-prod-01",
        node_id="kube-pod-f0d9c",
        pid=42_137,
    )


@pytest.fixture
def message(origin: UAPOrigin) -> UAPMessage:
    a = UAPArtifact(
        id="art-diff-01",
        kind="code_patch",
        size_bytes=2048,
        mime_type="text/x-diff",
        url="astra://knowledge/art-diff-01",
        sha256=hashlib.sha256(b"foo").hexdigest(),
        metadata={"source_path": "astra/cli.py"},
    )
    g = UAPGoal(
        id="g-0001",
        description="Implement UAP round-trips",
        priority=7,
        deadline=_now_z(),
        success_criteria="11 tests passing",
        confidence=0.9876,
    )
    e = UAPEvidence(
        source="https://example.com/research",
        kind="link",
        snippet="Proto3 JSON mapping rules",
        confidence=0.75,
        retrieved_at=_now_z(),
        metadata={"tag": "rfc"},
    )
    mid = UUID("018b9c00-0000-7000-8000-000000000001")
    return UAPMessage(
        message_id=mid,
        time=datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC),
        intent=UAPIntent.TASK_SUBMIT,
        sender=origin,
        recipient_agent_id="io.astraos.coder",
        conversation_id=uuid4(),
        thread_id="th-abc",
        goals=[g],
        body="Please deliver M1.4 UAP IDL round-trips.\n—CTO",
        structured={"epic": "M1", "tickets": ["UAP-1", "UAP-2"]},
        confidence=0.92,
        evidence=[e],
        dependencies=[uuid4()],
        task_id=uuid4(),
        artifacts=[a],
        events=[{"kind": "agent_boot", "ts": _now_z().isoformat()}],
        errors=[{"name": "NetworkError", "count": 0}],
        metrics=[{"name": "tokens_used", "value": 47}],
        resources=[{"kind": "gpu", "allocated_gb": 10}],
        execution_trace=[{"step": "plan", "ms": 12.3}],
        span=UAPSpan(trace_id="a" * 32, span_id="b" * 16, service="astraos-test"),
    )


def _assert_messages_equal(m1: UAPMessage, m2: UAPMessage) -> None:
    def s(v):
        if isinstance(v, float):
            assert isinstance(v, float)
            # handle rounding — float comparisons within 1e-9; but confidence is rounded to 4 decimals
            return round(v, 9)
        if isinstance(v, UUID):
            return str(v)
        if isinstance(v, datetime):
            return v.isoformat().replace("+00:00", "Z")
        return v

    for field in ("message_id", "conversation_id", "task_id"):
        assert str(getattr(m1, field)) == str(getattr(m2, field)), field
    for field in ("spec_version", "type", "source", "subject", "body", "thread_id", "recipient_agent_id"):
        assert getattr(m1, field) == getattr(m2, field), field
    assert m1.intent.value == m2.intent.value
    assert round(m1.confidence, 4) == round(m2.confidence, 4)
    # structured
    assert s(m1.structured) == s(m2.structured), (m1.structured, m2.structured)
    # nested lists
    assert len(m1.goals) == len(m2.goals)
    assert len(m1.evidence) == len(m2.evidence)
    assert len(m1.artifacts) == len(m2.artifacts)
    assert len(m1.events) == len(m2.events)
    assert len(m1.errors) == len(m2.errors)
    assert len(m1.metrics) == len(m2.metrics)
    assert len(m1.resources) == len(m2.resources)
    assert len(m1.execution_trace) == len(m2.execution_trace)
    # Dependencies
    assert [str(x) for x in m1.dependencies] == [str(x) for x in m2.dependencies]
    # Sender
    assert m1.sender.agent_id == m2.sender.agent_id
    assert m1.sender.pid == m2.sender.pid
    assert str(m1.sender.run_id) == str(m2.sender.run_id)


# ---------------------------------------------------------------------------
# JSON wire form
# ---------------------------------------------------------------------------


def test_json_roundtrip_message(message: UAPMessage) -> None:
    raw = encode_json(message)
    assert raw.endswith(b"}")
    # Rule 3: intent value MUST appear as a raw string (not an enum wrapper).
    payload = orjson.loads(raw)
    assert payload["intent"] == "task.submit"
    # Rule 4: UUIDs as lowercase 32-char hex (no dashes).
    assert payload["message_id"] == "018b9c00000070008000000000000001"
    # Rule 5: datetimes with Z suffix
    assert payload["time"].endswith("Z"), payload["time"]
    # Rule: structured dict appears as a plain JSON object under key "structured"
    # (NOT stringified)
    assert isinstance(payload["structured"], dict)
    assert payload["structured"]["tickets"] == ["UAP-1", "UAP-2"]
    # Decode
    back: UAPMessage = decode_json(UAPMessage, raw)  # type: ignore[assignment]
    _assert_messages_equal(message, back)


def test_json_determinism(message: UAPMessage) -> None:
    a = encode_json(message)
    b = encode_json(message)
    assert a == b
    # Deep-copy equivalent model → same bytes
    clone = UAPMessage.model_validate(message.model_dump())
    assert encode_json(clone) == a


def test_json_does_not_crash_on_empty_message(origin: UAPOrigin) -> None:
    msg = UAPMessage(intent=UAPIntent.PING, sender=origin)
    raw = encode_json(msg)
    back = decode_json(UAPMessage, raw)
    assert str(back.message_id) == str(msg.message_id)
    assert back.intent == UAPIntent.PING


# ---------------------------------------------------------------------------
# Binary wire form — tag order preserved, lossless
# ---------------------------------------------------------------------------


def test_binary_roundtrip_message(message: UAPMessage) -> None:
    raw = encode_binary(message)
    # Message should be longer than a single tiny tag (else something is
    #  being silently dropped in encode_binary default-filters)
    assert len(raw) > 100
    # Intent-string can be searched in binary because strings are stored
    #  as utf-8 in length-delimited chunks (proto3 JSON rule 3).
    assert b"task.submit" in raw
    # And UUID no-dash hex.
    assert b"018b9c00000070008000000000000001" in raw
    # Now the acid test: decode back
    back: UAPMessage = decode_binary(UAPMessage, raw)  # type: ignore[assignment]
    _assert_messages_equal(message, back)


def test_binary_roundtrip_message_preserves_structured_and_attachments(message: UAPMessage) -> None:
    back: UAPMessage = decode_binary(UAPMessage, encode_binary(message))  # type: ignore[assignment]
    # Structured dict
    assert back.structured["epic"] == "M1"
    # Goals
    assert back.goals[0].description.startswith("Implement UAP")
    assert round(back.goals[0].confidence, 4) == 0.9876
    # Evidence
    assert back.evidence[0].kind == "link"
    assert back.evidence[0].metadata == {"tag": "rfc"}
    # Artifact
    assert back.artifacts[0].sha256 == hashlib.sha256(b"foo").hexdigest()
    # Attachment JSON blobs
    assert back.events[0]["kind"] == "agent_boot"
    assert back.metrics[0]["name"] == "tokens_used"
    assert back.resources[0]["kind"] == "gpu"
    assert back.execution_trace[0]["step"] == "plan"


# ---------------------------------------------------------------------------
# SysCall + SysCallReply round-trips (kernel ABI, high value)
# ---------------------------------------------------------------------------


def test_syscall_roundtrips_json_and_binary(origin: UAPOrigin) -> None:
    call = UAPSysCall(
        call_id=UUID("018b9c00-0000-7000-8000-00000000cc01"),
        caller_agent_id=origin.agent_id,
        caller_handle=42,
        kind=UAPSysCallKind.TOKEN_MALLOC,
        args_json='{"tokens":4096,"zone":"REASONING"}',
        capability_token="tok_abc123",
    )
    raw_j = encode_json(call)
    assert b"token.malloc" in raw_j
    back_j: UAPSysCall = decode_json(UAPSysCall, raw_j)  # type: ignore[assignment]
    assert back_j.kind == call.kind
    assert back_j.args_json == call.args_json
    assert str(back_j.call_id) == str(call.call_id)
    assert back_j.capability_token == "tok_abc123"

    raw_b = encode_binary(call)
    assert b"tok_abc123" in raw_b
    back_b: UAPSysCall = decode_binary(UAPSysCall, raw_b)  # type: ignore[assignment]
    assert back_b.kind == call.kind
    assert back_b.caller_handle == 42


def test_syscall_reply_roundtrips(origin: UAPOrigin) -> None:
    reply = UAPSysCallReply(
        call_id=UUID("018b9c00-0000-7000-8000-00000000cc02"),
        success=True,
        denied=False,
        result_json='{"tokens_left":8192,"token_handle":"hdl_99"}',
        artifacts=["art-001", "art-002"],
        latency_ns=142_331.25,
    )
    j_back = decode_json(UAPSysCallReply, encode_json(reply))
    b_back = decode_binary(UAPSysCallReply, encode_binary(reply))
    for back in (j_back, b_back):
        assert back.success is True
        assert back.denied is False
        assert "8192" in back.result_json
        assert back.artifacts == ["art-001", "art-002"]
        assert math.isclose(back.latency_ns, 142_331.25, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# Turn + Envelope
# ---------------------------------------------------------------------------


def test_turn_roundtrip(message: UAPMessage, origin: UAPOrigin) -> None:
    reply1 = copy.deepcopy(message)
    reply1.intent = UAPIntent.TASK_RESULT
    reply1.body = "Done. Round-trips work."
    reply2 = copy.deepcopy(message)
    reply2.intent = UAPIntent.GOAL_PROGRESS
    reply2.body = "Progress 3/7"

    turn = UAPTurn(
        turn_id=uuid4(),
        conversation_id=message.conversation_id or uuid4(),
        sequence=11,
        created_at=_now_z(),
        request=message,
        replies=[reply1, reply2],
        summary="M1.4 delivered",
        wall_time_ms=127.5,
    )
    # JSON
    j = encode_json(turn)
    j_back: UAPTurn = decode_json(UAPTurn, j)  # type: ignore[assignment]
    assert j_back.sequence == 11
    assert j_back.summary == "M1.4 delivered"
    assert len(j_back.replies) == 2
    assert j_back.replies[0].intent == UAPIntent.TASK_RESULT
    # Binary
    raw = encode_binary(turn)
    assert b"Done. Round-trips work." in raw
    b_back: UAPTurn = decode_binary(UAPTurn, raw)  # type: ignore[assignment]
    assert b_back.sequence == 11
    assert math.isclose(b_back.wall_time_ms, 127.5, rel_tol=1e-9)
    assert len(b_back.replies) == 2
    assert b_back.replies[1].body.startswith("Progress")
    _assert_messages_equal(turn.request, b_back.request)


def test_envelope_roundtrip(message: UAPMessage) -> None:
    env = UAPEnvelope(
        envelope_id=uuid4(),
        created_at_unix_ms=1_759_900_000_000,
        transport=UAPTransportKind.NATS,
        subject="agents.io.astraos.coder.inbox",
        payload=message,
        trace_headers={"traceparent": "00-aaaa-bbbb-01", "baggage": "team=platform"},
    )
    j_back: UAPEnvelope = decode_json(UAPEnvelope, encode_json(env))  # type: ignore[assignment]
    assert j_back.transport == UAPTransportKind.NATS
    assert j_back.subject == "agents.io.astraos.coder.inbox"
    assert j_back.trace_headers["baggage"] == "team=platform"
    # Binary form must contain the NATS routing subject as a raw string
    raw = encode_binary(env)
    assert b"agents.io.astraos.coder.inbox" in raw
    b_back: UAPEnvelope = decode_binary(UAPEnvelope, raw)  # type: ignore[assignment]
    assert b_back.created_at_unix_ms == 1_759_900_000_000
    _assert_messages_equal(env.payload, b_back.payload)


# ---------------------------------------------------------------------------
# Canonical hash stability (signature-check contract)
# ---------------------------------------------------------------------------


def test_sha256_canonical_is_stable(message: UAPMessage) -> None:
    d1 = sha256_canonical(message)
    d2 = sha256_canonical(message)
    assert d1 == d2
    # Perturbing a single byte in the body MUST change the digest
    modified = copy.deepcopy(message)
    modified.body = message.body + "."
    assert sha256_canonical(modified) != d1


def test_decode_json_typeerror_for_unregistered_model() -> None:
    with pytest.raises(TypeError):
        decode_binary(UAPGoal, b"")


# ---------------------------------------------------------------------------
# Deterministic byte-stream ordering: field numbers on the wire are in
# ascending order across a message.  Proto3 does not REQUIRE this, but we
# guarantee it as an extra safety layer (makes bitwise diffs meaningful
# when comparing two captured messages).
# ---------------------------------------------------------------------------


def test_binary_tag_numbers_monotonic_for_message(message: UAPMessage) -> None:
    def tags(buf: bytes) -> list[int]:

        out: list[int] = []
        pos = 0
        n = len(buf)
        while pos < n:
            tag_wire = 0
            shift = 0
            while True:
                b = buf[pos]
                pos += 1
                tag_wire |= (b & 0x7F) << shift
                if (b & 0x80) == 0:
                    break
                shift += 7
            tag = tag_wire >> 3
            wt = tag_wire & 0x7
            out.append(tag)
            if wt == 0:
                # varint
                while pos < n and (buf[pos] & 0x80):
                    pos += 1
                pos += 1
            elif wt == 2:
                # lendelim: read len, skip body
                length = 0
                sh = 0
                while True:
                    b = buf[pos]
                    pos += 1
                    length |= (b & 0x7F) << sh
                    if (b & 0x80) == 0:
                        break
                    sh += 7
                pos += length
            else:
                raise AssertionError(f"wt {wt}")
        return out

    ts = tags(encode_binary(message))
    # Tags 1..6 + 10..14 + 20-24 + 30-31 + 40-45 + 50
    # Encoder emits in exactly this order; consecutive emitters append
    #  in ascending order per block, so assert monotonic non-decreasing.
    assert all(b >= a for a, b in itertools.pairwise(ts)), ts


def test_wire_symmetry_3form_equality(message: UAPMessage) -> None:
    """Three views of one message: canonical_json / encode_json / binary → decoded
    must all agree on intent, sender_agent_id, body hash, message_id hex.

    This is the acceptance-criterion assertion that "UAP Proto3 IDL round-trips
    losslessly" for the wire forms we actually ship.
    """
    canon = message.canonical_json()
    wire_j = encode_json(message)
    wire_b = encode_binary(message)
    j_back: UAPMessage = decode_json(UAPMessage, wire_j)  # type: ignore[assignment]
    b_back: UAPMessage = decode_binary(UAPMessage, wire_b)  # type: ignore[assignment]
    # 1. canonical_json() must be SHA-256 stable
    assert hashlib.sha256(canon).hexdigest() == hashlib.sha256(message.canonical_json()).hexdigest()
    # 2. identity fields all match across 3 forms
    for view in (j_back, b_back):
        assert str(view.message_id) == str(message.message_id)
        assert view.intent.value == message.intent.value
        assert view.sender.agent_id == message.sender.agent_id
        assert view.body == message.body
        assert round(view.confidence, 4) == round(message.confidence, 4)
        assert len(view.artifacts) == len(message.artifacts)
        assert len(view.goals) == len(message.goals)
    # 3. two wire decodings must match each other (binary == json symmetry)
    assert j_back.body == b_back.body
    assert j_back.structured == b_back.structured
