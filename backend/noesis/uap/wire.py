"""
Wire encoder / decoder for the Universal Agent Protocol.

Two wire forms, both LOSSLESS round-trippable against the schemas in
``schemas/uap/v1/uap.proto``:

1. **JSON** — Proto3-JSON-shaped bytes with deterministic ``SORT_KEYS``
   ordering.  All UUIDs are daseless 32-char lowercase hex strings; all
   datetimes are RFC 3339 UTC with ``Z`` suffix.  Every non-private
   message in ``astra.uap`` can be serialised this way.

2. **Binary** — Tag-length-value record format.  This is NOT the standard
   Protobuf wire format (to avoid a runtime dep on ``protobuf`` / ``grpcio``
   in the base M1 runtime), but the *tag numbers* on every field match
   EXACTLY the ``.proto`` schema tag numbers.  That means the binary form
   can be stream-converted to Protobuf binary by a translator that only
   needs to know the mapping of tag→wire type — the Python reference
   encoder doesn't reorder or renumber anything.

Wire rules (must hold for BOTH forms):
  * UUIDs → 32-char lowercase ASCII hex, no dashes.  (Rule 4.)
  * datetimes → RFC 3339 UTC with ``Z`` suffix.  (Rule 5.)
  * StrEnum values → their .value strings.  (Rule 3.)
  * ``0`` / ``""`` / ``false`` / ``None`` optional-fields MAY be omitted
    from JSON (Proto3 semantics) but are accepted by the decoder.
"""

from __future__ import annotations

import hashlib
import struct
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

import orjson
from pydantic import BaseModel

from noesis.uap import (
    UAPArtifact,
    UAPEnvelope,
    UAPEvidence,
    UAPGoal,
    UAPMessage,
    UAPOrigin,
    UAPSpan,
    UAPSysCall,
    UAPSysCallReply,
    UAPTurn,
)

# ---------------------------------------------------------------------------
# Normalisation helpers — make dicts match proto3 JSON expectations
# ---------------------------------------------------------------------------


def _norm_value(v: Any) -> Any:
    if isinstance(v, UUID):
        return v.hex
    if isinstance(v, datetime):
        v = v.replace(tzinfo=UTC) if v.tzinfo is None else v.astimezone(UTC)
        return v.isoformat().replace("+00:00", "Z")
    if isinstance(v, StrEnum):
        return v.value
    if isinstance(v, dict):
        return {k: _norm_value(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_norm_value(x) for x in v]
    if isinstance(v, BaseModel):
        return _norm_value(v.model_dump(mode="python"))
    return v


def _json_dump(obj: Any) -> bytes:
    return orjson.dumps(_norm_value(obj), option=orjson.OPT_SORT_KEYS | orjson.OPT_UTC_Z)


# ---------------------------------------------------------------------------
# Denormalisation — turn proto3-JSON dicts back into Python/Pydantic-native
# ---------------------------------------------------------------------------


def _uuid(s: Any) -> str | None:
    if not s:
        return None
    if isinstance(s, UUID):
        return s.hex
    # Accept hex OR dashed; always normalise via UUID() round-trip.
    return UUID(str(s)).hex


def _dt(s: str | None) -> Any:
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def _coerce(cls: type[BaseModel], data: Any) -> BaseModel:
    if isinstance(data, cls):
        return data

    def _walk(node: Any, t: type) -> Any:
        if t is UUID:
            return _uuid(node)
        if t is datetime:
            return _dt(node)
        if isinstance(node, list):
            return [_walk(x, object) for x in node]
        if isinstance(node, dict):
            return {k: _walk(v, object) for k, v in node.items()}
        return node

    return cls.model_validate(_walk(data, cls))


# ---------------------------------------------------------------------------
# JSON wire form — public functions
# ---------------------------------------------------------------------------


def encode_json(message: BaseModel) -> bytes:
    """Encode a UAP pydantic message as Proto3-shaped JSON bytes.

    Byte-for-byte deterministic (sorted keys, canonical dates/UUIDs).
    """
    return _json_dump(message.model_dump(mode="python"))


def decode_json(cls: type[BaseModel], raw: bytes | bytearray | str) -> BaseModel:
    """Parse JSON bytes produced by :func:`encode_json` back into a model."""
    raw_bytes = raw.encode() if isinstance(raw, str) else bytes(raw)
    data = orjson.loads(raw_bytes)
    return _coerce(cls, data)


# ---------------------------------------------------------------------------
# Binary wire form — TLV with exact proto tag numbers per uap.proto
# ---------------------------------------------------------------------------

# Wire types
_WT_VARINT = 0
_WT_LENDELIM = 2


def _t(tag: int, wtype: int) -> int:
    return (tag << 3) | wtype


def _enc_varint(v: int) -> bytes:
    # unsigned LEB128 (matches protobuf base-128 varint semantics).
    if v < 0:
        v += 1 << 64
    out = bytearray()
    while True:
        chunk = v & 0x7F
        v >>= 7
        if v:
            out.append(chunk | 0x80)
        else:
            out.append(chunk)
            return bytes(out)


def _enc_len(tag: int, body: bytes) -> bytes:
    return _enc_varint(_t(tag, _WT_LENDELIM)) + _enc_varint(len(body)) + body


def _enc_str(tag: int, s: str) -> bytes:
    return _enc_len(tag, s.encode("utf-8"))


def _enc_bytes(tag: int, b: bytes) -> bytes:
    return _enc_len(tag, b)


def _enc_bool(tag: int, x: bool) -> bytes:
    return _enc_varint(_t(tag, _WT_VARINT)) + _enc_varint(1 if x else 0)


def _enc_uint(tag: int, x: int) -> bytes:
    return _enc_varint(_t(tag, _WT_VARINT)) + _enc_varint(x)


def _enc_float(tag: int, x: float) -> bytes:
    # Little-endian 64-bit IEEE754 double, length-delimited with a body of 8 bytes.
    return _enc_len(tag, struct.pack("<d", float(x)))


def _enc_strs(tag: int, xs: list[str]) -> bytes:
    return b"".join(_enc_str(tag, s) for s in xs)


def _enc_objs(tag: int, objs: list[BaseModel], enc_one) -> bytes:
    return b"".join(_enc_len(tag, enc_one(x)) for x in objs)


def _enc_map(tag: int, mapping: dict) -> bytes:
    # Proto map = repeated {1:key, 2:value} submessages.
    out = b""
    for k, v in mapping.items():
        entry = _enc_str(1, str(k)) + _enc_str(2, str(v))
        out += _enc_len(tag, entry)
    return out


def _enc_optional(tag: int, value: Any, enc) -> bytes:
    if value is None or value in {"", 0} or value is False:
        # Proto3: omit zero/empty scalars; encoders that emit them are also
        # accepted by the decoder, but the canonical form omits.
        return b""
    return enc(tag, value)


# ---- per-message encoders: tag numbers MUST match schemas/uap/v1/uap.proto ---


def _enc_origin(o: UAPOrigin) -> bytes:
    return (
        _enc_str(1, o.agent_id)
        + _enc_str(2, str(o.agent_type))
        + _enc_optional(3, _uuid(o.run_id) if o.run_id else None, _enc_str)
        + _enc_optional(4, o.workspace_id, _enc_str)
        + _enc_optional(5, o.node_id, _enc_str)
        + _enc_optional(6, o.pid, _enc_uint)
        + _enc_optional(7, o.signature, _enc_str)
        + _enc_optional(8, o.signer_issuer, _enc_str)
    )


def _enc_evidence(e: UAPEvidence) -> bytes:
    meta = {k: str(v) for k, v in (e.metadata or {}).items()}
    return (
        _enc_str(1, e.source)
        + _enc_str(2, e.kind)
        + _enc_str(3, e.snippet)
        + _enc_float(4, e.confidence)
        + _enc_str(5, _norm_value(e.retrieved_at))
        + _enc_map(6, meta)
    )


def _enc_goal(g: UAPGoal) -> bytes:
    return (
        _enc_str(1, g.id)
        + _enc_str(2, g.description)
        + _enc_uint(3, int(g.priority))
        + _enc_optional(4, _norm_value(g.deadline) if g.deadline else None, _enc_str)
        + _enc_str(5, g.success_criteria)
        + _enc_optional(6, g.parent_goal_id, _enc_str)
        + _enc_float(7, g.confidence)
    )


def _enc_artifact(a: UAPArtifact) -> bytes:
    meta = {k: str(v) for k, v in (a.metadata or {}).items()}
    return (
        _enc_str(1, a.id)
        + _enc_str(2, a.kind)
        + _enc_optional(3, a.size_bytes, _enc_uint)
        + _enc_optional(4, a.mime_type, _enc_str)
        + _enc_optional(5, a.url, _enc_str)
        + _enc_optional(6, a.sha256, _enc_str)
        + _enc_map(7, meta)
    )


def _enc_span(s: UAPSpan) -> bytes:
    return (
        _enc_optional(1, s.trace_id, _enc_str)
        + _enc_optional(2, s.span_id, _enc_str)
        + _enc_optional(3, s.parent_span_id, _enc_str)
        + _enc_str(4, s.service)
    )


def _enc_message(m: UAPMessage) -> bytes:
    # Deconstruct structured dict → JSON string (proto field 22).
    structured_json = orjson.dumps(m.structured).decode() if m.structured else ""
    # Flatten non-scalar attachment lists: each one is a repeated JSON string.
    events_json = [orjson.dumps(x).decode() for x in m.events]
    errors_json = [orjson.dumps(x).decode() for x in m.errors]
    metrics_json = [orjson.dumps(x).decode() for x in m.metrics]
    resources_json = [orjson.dumps(x).decode() for x in m.resources]
    trace_json = [orjson.dumps(x).decode() for x in m.execution_trace]
    return (
        _enc_str(1, m.spec_version)
        + _enc_str(2, UUID(str(m.message_id)).hex)
        + _enc_str(3, _norm_value(m.time))
        + _enc_str(4, m.type)
        + _enc_str(5, m.source)
        + _enc_str(6, m.subject)
        + _enc_str(10, str(m.intent.value))
        + _enc_len(11, _enc_origin(m.sender))
        + _enc_optional(12, m.recipient_agent_id, _enc_str)
        + _enc_optional(13, _uuid(m.conversation_id) if m.conversation_id else None, _enc_str)
        + _enc_optional(14, m.thread_id, _enc_str)
        + _enc_objs(20, m.goals, _enc_goal)
        + _enc_str(21, m.body)
        + _enc_optional(22, structured_json, _enc_str)
        + _enc_float(23, m.confidence)
        + _enc_objs(24, m.evidence, _enc_evidence)
        + _enc_strs(30, [UUID(str(x)).hex for x in m.dependencies])
        + _enc_optional(31, _uuid(m.task_id) if m.task_id else None, _enc_str)
        + _enc_objs(40, m.artifacts, _enc_artifact)
        + _enc_strs(41, events_json)
        + _enc_strs(42, errors_json)
        + _enc_strs(43, metrics_json)
        + _enc_strs(44, resources_json)
        + _enc_strs(45, trace_json)
        + (_enc_len(50, _enc_span(m.span)) if m.span and any([m.span.trace_id, m.span.span_id, m.span.parent_span_id]) else b"")
    )


def _enc_turn(t: UAPTurn) -> bytes:
    return (
        _enc_str(1, UUID(str(t.turn_id)).hex)
        + _enc_str(2, UUID(str(t.conversation_id)).hex)
        + _enc_uint(3, int(t.sequence))
        + _enc_str(4, _norm_value(t.created_at))
        + _enc_len(5, _enc_message(t.request))
        + _enc_objs(6, t.replies, _enc_message)
        + _enc_optional(7, t.summary, _enc_str)
        + _enc_float(8, t.wall_time_ms)
    )


def _enc_envelope(e: UAPEnvelope) -> bytes:
    return (
        _enc_str(1, UUID(str(e.envelope_id)).hex)
        + _enc_uint(2, int(e.created_at_unix_ms))
        + _enc_str(3, str(e.transport.value))
        + _enc_optional(4, e.subject, _enc_str)
        + _enc_len(5, _enc_message(e.payload))
        + _enc_map(6, e.trace_headers or {})
    )


def _enc_syscall(s: UAPSysCall) -> bytes:
    return (
        _enc_str(1, UUID(str(s.call_id)).hex)
        + _enc_uint(2, int(s.issued_at_unix_ns))
        + _enc_str(3, s.caller_agent_id)
        + _enc_uint(4, int(s.caller_handle))
        + _enc_str(5, str(s.kind.value))
        + _enc_str(6, s.args_json)
        + _enc_optional(7, s.capability_token, _enc_str)
    )


def _enc_syscall_reply(r: UAPSysCallReply) -> bytes:
    return (
        _enc_str(1, UUID(str(r.call_id)).hex)
        + _enc_uint(2, int(r.completed_at_unix_ns))
        + _enc_bool(3, bool(r.success))
        + _enc_bool(4, bool(r.denied))
        + _enc_optional(5, r.deny_reason, _enc_str)
        + _enc_optional(6, r.result_json, _enc_str)
        + _enc_strs(7, list(r.artifacts or []))
        + _enc_float(8, float(r.latency_ns))
    )


def encode_binary(message: BaseModel) -> bytes:
    """Encode a UAP message as binary TLV bytes (tag numbers match ``.proto``)."""
    if isinstance(message, UAPMessage):
        return _enc_message(message)
    if isinstance(message, UAPTurn):
        return _enc_turn(message)
    if isinstance(message, UAPEnvelope):
        return _enc_envelope(message)
    if isinstance(message, UAPSysCall):
        return _enc_syscall(message)
    if isinstance(message, UAPSysCallReply):
        return _enc_syscall_reply(message)
    raise TypeError(f"encode_binary: unsupported model type {type(message).__name__}")


# ---- binary decoder --------------------------------------------------------


def _dec_varint(buf: bytes, pos: int) -> tuple[int, int]:
    result = 0
    shift = 0
    start = pos
    while pos < len(buf):
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if (b & 0x80) == 0:
            return result, pos
        shift += 7
        if shift > 63:
            raise ValueError(f"varint overflow at pos {start}")
    raise ValueError(f"unterminated varint at pos {start}")


def _split(buf: bytes) -> list[tuple[int, int, bytes]]:
    """Return list of (tag, wtype, body_bytes) for every top-level field."""
    pos = 0
    n = len(buf)
    fields: list[tuple[int, int, bytes]] = []
    while pos < n:
        tag_wire, pos = _dec_varint(buf, pos)
        tag = tag_wire >> 3
        wt = tag_wire & 0x7
        if wt == _WT_VARINT:
            v, pos = _dec_varint(buf, pos)
            # body is the varint integer itself; use 8-byte little-endian fixed form
            # so downstream consumers can treat it as bytes if needed.
            fields.append((tag, wt, v.to_bytes(8, "little", signed=False)))
        elif wt == _WT_LENDELIM:
            length, pos = _dec_varint(buf, pos)
            end = pos + length
            if end > n:
                raise ValueError(f"lendelim overshoot at pos {pos - 1} len {length}")
            fields.append((tag, wt, buf[pos:end]))
            pos = end
        else:
            raise ValueError(f"unsupported wire type {wt} tag {tag} pos {pos - 1}")
    return fields


def _fv(tags: list[tuple[int, int, bytes]], tag: int, wtype: int) -> list[bytes]:
    return [body for (t, w, body) in tags if t == tag and w == wtype]


def _fv_first(tags: list[tuple[int, int, bytes]], tag: int, wtype: int) -> bytes | None:
    xs = _fv(tags, tag, wtype)
    return xs[0] if xs else None


def _as_varint_int(body: bytes) -> int:
    return int.from_bytes(body[:8], "little", signed=False)


def _as_str(body: bytes) -> str:
    return body.decode("utf-8")


def _as_float(body: bytes) -> float:
    return struct.unpack("<d", body[:8])[0]


def _as_bool(body: bytes) -> bool:
    return _as_varint_int(body) != 0


def _dec_map(body_list: list[bytes]) -> dict[str, str]:
    out: dict[str, str] = {}
    for blk in body_list:
        fields = _split(blk)
        key = _as_str(_fv_first(fields, 1, _WT_LENDELIM) or b"")
        val = _as_str(_fv_first(fields, 2, _WT_LENDELIM) or b"")
        if key:
            out[key] = val
    return out


def _dec_origin(buf: bytes) -> dict[str, Any]:
    t = _split(buf)
    return {
        "agent_id": _as_str(_fv_first(t, 1, _WT_LENDELIM) or b""),
        "agent_type": _as_str(_fv_first(t, 2, _WT_LENDELIM) or b"unknown"),
        "run_id": _uuid(_as_str(b)) if (b := _fv_first(t, 3, _WT_LENDELIM)) else None,
        "workspace_id": _as_str(b) if (b := _fv_first(t, 4, _WT_LENDELIM)) else None,
        "node_id": _as_str(b) if (b := _fv_first(t, 5, _WT_LENDELIM)) else "",
        "pid": _as_varint_int(b) if (b := _fv_first(t, 6, _WT_VARINT)) else None,
        "signature": _as_str(b) if (b := _fv_first(t, 7, _WT_LENDELIM)) else "",
        "signer_issuer": _as_str(b) if (b := _fv_first(t, 8, _WT_LENDELIM)) else "",
    }


def _dec_evidence(buf: bytes) -> dict[str, Any]:
    t = _split(buf)
    meta = _dec_map(_fv(t, 6, _WT_LENDELIM))
    return {
        "source": _as_str(_fv_first(t, 1, _WT_LENDELIM) or b""),
        "kind": _as_str(_fv_first(t, 2, _WT_LENDELIM) or b"text"),
        "snippet": _as_str(_fv_first(t, 3, _WT_LENDELIM) or b""),
        "confidence": _as_float(b) if (b := _fv_first(t, 4, _WT_LENDELIM)) else 1.0,
        "retrieved_at": _dt(_as_str(b)) if (b := _fv_first(t, 5, _WT_LENDELIM)) else None,
        "metadata": meta,
    }


def _dec_goal(buf: bytes) -> dict[str, Any]:
    t = _split(buf)
    return {
        "id": _as_str(_fv_first(t, 1, _WT_LENDELIM) or b""),
        "description": _as_str(_fv_first(t, 2, _WT_LENDELIM) or b""),
        "priority": _as_varint_int(b) if (b := _fv_first(t, 3, _WT_VARINT)) else 5,
        "deadline": _dt(_as_str(b)) if (b := _fv_first(t, 4, _WT_LENDELIM)) else None,
        "success_criteria": _as_str(_fv_first(t, 5, _WT_LENDELIM) or b""),
        "parent_goal_id": _as_str(b) if (b := _fv_first(t, 6, _WT_LENDELIM)) else "",
        "confidence": _as_float(b) if (b := _fv_first(t, 7, _WT_LENDELIM)) else 1.0,
    }


def _dec_artifact(buf: bytes) -> dict[str, Any]:
    t = _split(buf)
    meta = _dec_map(_fv(t, 7, _WT_LENDELIM))
    return {
        "id": _as_str(_fv_first(t, 1, _WT_LENDELIM) or b""),
        "kind": _as_str(_fv_first(t, 2, _WT_LENDELIM) or b"blob"),
        "size_bytes": _as_varint_int(b) if (b := _fv_first(t, 3, _WT_VARINT)) else None,
        "mime_type": _as_str(b) if (b := _fv_first(t, 4, _WT_LENDELIM)) else "",
        "url": _as_str(b) if (b := _fv_first(t, 5, _WT_LENDELIM)) else "",
        "sha256": _as_str(b) if (b := _fv_first(t, 6, _WT_LENDELIM)) else "",
        "metadata": meta,
    }


def _dec_span(buf: bytes) -> dict[str, Any]:
    t = _split(buf)
    return {
        "trace_id": _as_str(b) if (b := _fv_first(t, 1, _WT_LENDELIM)) else "",
        "span_id": _as_str(b) if (b := _fv_first(t, 2, _WT_LENDELIM)) else "",
        "parent_span_id": _as_str(b) if (b := _fv_first(t, 3, _WT_LENDELIM)) else "",
        "service": _as_str(_fv_first(t, 4, _WT_LENDELIM) or b"noesis"),
    }


def _dec_message(buf: bytes) -> dict[str, Any]:
    t = _split(buf)
    dep_ids = [UUID(hex=_as_str(x)) for x in _fv(t, 30, _WT_LENDELIM)]
    goals = [_dec_goal(x) for x in _fv(t, 20, _WT_LENDELIM)]
    evs = [_dec_evidence(x) for x in _fv(t, 24, _WT_LENDELIM)]
    arts = [_dec_artifact(x) for x in _fv(t, 40, _WT_LENDELIM)]
    events = [orjson.loads(x) for x in _fv(t, 41, _WT_LENDELIM)]
    errors = [orjson.loads(x) for x in _fv(t, 42, _WT_LENDELIM)]
    metrics = [orjson.loads(x) for x in _fv(t, 43, _WT_LENDELIM)]
    resources = [orjson.loads(x) for x in _fv(t, 44, _WT_LENDELIM)]
    traces = [orjson.loads(x) for x in _fv(t, 45, _WT_LENDELIM)]
    structured_json_raw = _fv_first(t, 22, _WT_LENDELIM)
    structured = orjson.loads(structured_json_raw) if structured_json_raw else {}
    conv_raw = _fv_first(t, 13, _WT_LENDELIM)
    task_raw = _fv_first(t, 31, _WT_LENDELIM)
    span_raw = _fv_first(t, 50, _WT_LENDELIM)
    sender_raw = _fv_first(t, 11, _WT_LENDELIM)
    return {
        "spec_version": _as_str(_fv_first(t, 1, _WT_LENDELIM) or b"1.0"),
        "message_id": UUID(hex=_as_str(_fv_first(t, 2, _WT_LENDELIM) or (b"0" * 32))),
        "time": _dt(_as_str(_fv_first(t, 3, _WT_LENDELIM) or b"")),
        "type": _as_str(_fv_first(t, 4, _WT_LENDELIM) or b""),
        "source": _as_str(_fv_first(t, 5, _WT_LENDELIM) or b"noesis://kernel"),
        "subject": _as_str(_fv_first(t, 6, _WT_LENDELIM) or b""),
        "intent": _as_str(_fv_first(t, 10, _WT_LENDELIM) or b"task.submit"),
        "sender": _dec_origin(sender_raw) if sender_raw else None,
        "recipient_agent_id": _as_str(b) if (b := _fv_first(t, 12, _WT_LENDELIM)) else "",
        "conversation_id": UUID(hex=_as_str(conv_raw)) if conv_raw else None,
        "thread_id": _as_str(b) if (b := _fv_first(t, 14, _WT_LENDELIM)) else "",
        "goals": goals,
        "body": _as_str(_fv_first(t, 21, _WT_LENDELIM) or b""),
        "structured": structured,
        "confidence": _as_float(b) if (b := _fv_first(t, 23, _WT_LENDELIM)) else 1.0,
        "evidence": evs,
        "dependencies": dep_ids,
        "task_id": UUID(hex=_as_str(task_raw)) if task_raw else None,
        "artifacts": arts,
        "events": events,
        "errors": errors,
        "metrics": metrics,
        "resources": resources,
        "execution_trace": traces,
        "span": _dec_span(span_raw) if span_raw else {},
    }


def _dec_turn(buf: bytes) -> dict[str, Any]:
    t = _split(buf)
    replies = [_dec_message(x) for x in _fv(t, 6, _WT_LENDELIM)]
    req_raw = _fv_first(t, 5, _WT_LENDELIM)
    return {
        "turn_id": UUID(hex=_as_str(_fv_first(t, 1, _WT_LENDELIM) or (b"0" * 32))),
        "conversation_id": UUID(hex=_as_str(_fv_first(t, 2, _WT_LENDELIM) or (b"0" * 32))),
        "sequence": _as_varint_int(b) if (b := _fv_first(t, 3, _WT_VARINT)) else 0,
        "created_at": _dt(_as_str(b)) if (b := _fv_first(t, 4, _WT_LENDELIM)) else None,
        "request": _dec_message(req_raw) if req_raw else None,
        "replies": replies,
        "summary": _as_str(b) if (b := _fv_first(t, 7, _WT_LENDELIM)) else "",
        "wall_time_ms": _as_float(b) if (b := _fv_first(t, 8, _WT_LENDELIM)) else 0.0,
    }


def _dec_envelope(buf: bytes) -> dict[str, Any]:
    t = _split(buf)
    payload_raw = _fv_first(t, 5, _WT_LENDELIM)
    return {
        "envelope_id": UUID(hex=_as_str(_fv_first(t, 1, _WT_LENDELIM) or (b"0" * 32))),
        "created_at_unix_ms": _as_varint_int(b) if (b := _fv_first(t, 2, _WT_VARINT)) else 0,
        "transport": _as_str(_fv_first(t, 3, _WT_LENDELIM) or b"local"),
        "subject": _as_str(b) if (b := _fv_first(t, 4, _WT_LENDELIM)) else "",
        "payload": _dec_message(payload_raw) if payload_raw else None,
        "trace_headers": _dec_map(_fv(t, 6, _WT_LENDELIM)),
    }


def _dec_syscall(buf: bytes) -> dict[str, Any]:
    t = _split(buf)
    return {
        "call_id": UUID(hex=_as_str(_fv_first(t, 1, _WT_LENDELIM) or (b"0" * 32))),
        "issued_at_unix_ns": _as_varint_int(b) if (b := _fv_first(t, 2, _WT_VARINT)) else 0,
        "caller_agent_id": _as_str(_fv_first(t, 3, _WT_LENDELIM) or b""),
        "caller_handle": _as_varint_int(b) if (b := _fv_first(t, 4, _WT_VARINT)) else 0,
        "kind": _as_str(_fv_first(t, 5, _WT_LENDELIM) or b"memory.read"),
        "args_json": _as_str(_fv_first(t, 6, _WT_LENDELIM) or b"{}"),
        "capability_token": _as_str(b) if (b := _fv_first(t, 7, _WT_LENDELIM)) else "",
    }


def _dec_syscall_reply(buf: bytes) -> dict[str, Any]:
    t = _split(buf)
    artifacts = [_as_str(x) for x in _fv(t, 7, _WT_LENDELIM)]
    return {
        "call_id": UUID(hex=_as_str(_fv_first(t, 1, _WT_LENDELIM) or (b"0" * 32))),
        "completed_at_unix_ns": _as_varint_int(b) if (b := _fv_first(t, 2, _WT_VARINT)) else 0,
        "success": _as_bool(b) if (b := _fv_first(t, 3, _WT_VARINT)) else False,
        "denied": _as_bool(b) if (b := _fv_first(t, 4, _WT_VARINT)) else False,
        "deny_reason": _as_str(b) if (b := _fv_first(t, 5, _WT_LENDELIM)) else "",
        "result_json": _as_str(b) if (b := _fv_first(t, 6, _WT_LENDELIM)) else "{}",
        "artifacts": artifacts,
        "latency_ns": _as_float(b) if (b := _fv_first(t, 8, _WT_LENDELIM)) else 0.0,
    }


def decode_binary(cls: type[BaseModel], raw: bytes) -> BaseModel:
    """Decode binary bytes produced by :func:`encode_binary` back into a model."""
    if cls is UAPMessage:
        data = _dec_message(bytes(raw))
    elif cls is UAPTurn:
        data = _dec_turn(bytes(raw))
    elif cls is UAPEnvelope:
        data = _dec_envelope(bytes(raw))
    elif cls is UAPSysCall:
        data = _dec_syscall(bytes(raw))
    elif cls is UAPSysCallReply:
        data = _dec_syscall_reply(bytes(raw))
    else:
        raise TypeError(f"decode_binary: unsupported model type {cls.__name__}")
    return _coerce(cls, data)


# ---------------------------------------------------------------------------
# Test helper: determinism checks (canonical hash stability)
# ---------------------------------------------------------------------------


def sha256_canonical(message: BaseModel) -> str:
    """Double-safety hash: SHA-256 of encode_json() bytes.

    If you change any UAP field and *don't* bump spec_version, at least one
    round-trip test will show this hash changing.
    """
    return hashlib.sha256(encode_json(message)).hexdigest()


__all__ = [
    "decode_binary",
    "decode_json",
    "encode_binary",
    "encode_json",
    "sha256_canonical",
]
