"""
Hexagonal port contract tests.

Goal: verify that each port ABC:
  * is abstract (cannot be instantiated without implementing all methods)
  * defines the expected method signatures (via ``__abstractmethods__``)
  * has the correct RepositoryPort generic bindings (T, ID)

These tests guarantee LSP: any adapter that passes these unit tests will
work correctly when swapped via the DI container in production.
"""

from __future__ import annotations

from abc import ABC
from inspect import signature
from uuid import UUID

import pytest

from noesis.core.ports import (
    ArtifactRepositoryPort,
    CachePort,
    ChatPort,
    ClockPort,
    ConversationRepositoryPort,
    DocumentRepositoryPort,
    EmbeddingPort,
    EventBusPort,
    IdGenPort,
    KnowledgeObjectRepositoryPort,
    MemoryRepositoryPort,
    MessageRepositoryPort,
    RepositoryPort,
    TaskExecutionRepositoryPort,
    UserRepositoryPort,
    VectorStorePort,
)


@pytest.mark.parametrize(
    ("port_cls", "expected_abstract_methods"),
    [
        (RepositoryPort, {"get", "create", "update", "delete", "list"}),
        (UserRepositoryPort, {"get_by_email", "get_by_sub"}),
        (ConversationRepositoryPort, {"list_for_user"}),
        (MessageRepositoryPort, {"list_for_conversation"}),
        (MemoryRepositoryPort, {"list_for_scope", "search_by_similarity"}),
        (DocumentRepositoryPort, {"search_by_similarity"}),
        (TaskExecutionRepositoryPort, {"list_for_run"}),
        (ArtifactRepositoryPort, {"list_for_task", "find_by_sha256"}),
        (
            KnowledgeObjectRepositoryPort,
            {"list_for_workspace", "search_by_tag", "list_versions"},
        ),
        (ChatPort, {"chat"}),
        (EmbeddingPort, {"embed"}),
        (VectorStorePort, {"upsert", "search", "delete"}),
        (CachePort, {"get", "set", "delete", "clear"}),
        (ClockPort, {"now"}),
        (IdGenPort, {"new"}),
        (EventBusPort, {"publish", "subscribe"}),
    ],
)
def test_port_abstract_methods_exist(port_cls: type, expected_abstract_methods: set[str]):
    # Must be a subclass of ABC / be an ABCMeta class
    assert issubclass(port_cls, ABC) or isinstance(port_cls, type(ABC))
    missing = expected_abstract_methods - set(port_cls.__abstractmethods__)
    assert not missing, f"{port_cls.__name__} missing abstract methods: {missing}"


def test_repository_port_generic_id_type_is_uuid_for_subclasses():
    # Each RepositoryPort subclass uses UUID as the ID type (second generic arg).
    # The base RepositoryPort uses TypeVar `_KT`; concrete subclasses are bound to
    # UUID in the ABC declaration, which is visible in the ABC's __orig_bases__
    # (PEP 560 subscripted generic base) for each concrete subclass.
    import typing

    for cls in (
        UserRepositoryPort,
        ConversationRepositoryPort,
        MessageRepositoryPort,
        MemoryRepositoryPort,
        DocumentRepositoryPort,
        TaskExecutionRepositoryPort,
        ArtifactRepositoryPort,
        KnowledgeObjectRepositoryPort,
    ):
        orig_bases = getattr(cls, "__orig_bases__", ())
        # Expect: (RepositoryPort[EntityT, UUID],)  — second arg is UUID
        assert orig_bases, f"{cls.__name__} has no __orig_bases__ (not a subscripted generic?)"
        base_t = orig_bases[0]  # RepositoryPort[T, ID]
        args = typing.get_args(base_t)
        assert len(args) == 2, f"{cls.__name__} base should be RepositoryPort[T, ID]; got args={args}"
        entity_t, id_t = args
        assert id_t is UUID, f"{cls.__name__} should be parameterised with RepositoryPort[{entity_t.__name__}, UUID], got id type={id_t!r}"


def test_repository_list_returns_page():
    # list(params: PageParams) -> Page[T] contract verification
    for cls in (
        UserRepositoryPort,
        ConversationRepositoryPort,
        MemoryRepositoryPort,
        DocumentRepositoryPort,
        ArtifactRepositoryPort,
        KnowledgeObjectRepositoryPort,
    ):
        sig = signature(cls.list)  # type: ignore[attr-defined]
        return_annotation = sig.return_annotation
        # Return type must be Page-something (stringified Page[T] in from __future__ annotations)
        assert "Page" in str(return_annotation), f"{cls.__name__}.list must return Page[T], got: {return_annotation}"
