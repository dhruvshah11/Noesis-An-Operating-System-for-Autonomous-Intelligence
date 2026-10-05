"""
Dependency-injection container for Noesis.

Instead of scattering ``get_settings()`` calls + provider factories across
every file, we build ONE :class:`Container` and pass it down (FastAPI
``Depends(get_container)``, CLI ``build_default_container``, tests
``build_test_container``).

The design is deliberately small:
    * Register an abstract -> concrete factory pair with ``.register(Port, factory)``
    * Resolve instances with ``await .get(Port)`` (lazy + cached)
    * Tear down everything with ``await .aclose()``

This keeps service constructors *honest* about their dependencies — no global
singletons hiding in module scope.  In tests you wire fake adapters for
ChatPort / RepositoryPort and the rest of the system works unchanged.

Example::

    from noesis.core.di import build_default_container
    container = await build_default_container()
    chat = await container.get(ChatPort)  # real provider if keys present
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC
from typing import TYPE_CHECKING, Any, TypeVar
from uuid import uuid4

from noesis.logging import get_logger

if TYPE_CHECKING:
    from types import TracebackType

log = get_logger(__name__)

T = TypeVar("T")


class Container:
    """Minimal async-safe DI container."""

    def __init__(self) -> None:
        # Abstract type -> (factory callable, cached_instance)
        self._registry: dict[type, tuple[Callable[[Container], Awaitable[Any] | Any], Any]] = {}
        self._registry_instances: dict[type, Any] = {}
        # Async cleanup callbacks (e.g. aclose() on httpx clients)
        self._closers: list[Callable[[], Awaitable[None]]] = []
        self._closed = False

    # --- Registration API ---------------------------------------------------

    def register(
        self,
        abstract: type[T],
        factory: Callable[[Container], Awaitable[T] | T],
        *,
        singleton: bool = True,
        on_close: Callable[[T], Awaitable[None]] | None = None,
    ) -> None:
        """Register a factory for an abstract type."""
        if abstract in self._registry:
            log.warning("di.replaced", abstract=abstract.__name__)
        self._registry[abstract] = (factory, singleton)
        if on_close is not None:
            self._closers.append(_make_closer(self, abstract, on_close))

    # --- Resolution API -----------------------------------------------------

    async def get(self, abstract: type[T]) -> T:
        if self._closed:
            raise RuntimeError(f"DI Container is closed; cannot resolve {abstract.__name__}")
        cached = self._registry_instances.get(abstract)
        if cached is not None:
            return cached  # type: ignore[no-any-return]
        if abstract not in self._registry:
            raise KeyError(f"DI Container has no factory for {abstract.__name__}. Register it in build_default_container or wire a test double.")
        factory, singleton = self._registry[abstract]
        instance = factory(self)
        if isinstance(instance, Awaitable):
            instance = await instance
        if singleton:
            self._registry_instances[abstract] = instance
        return instance  # type: ignore[no-any-return]

    # --- Lifecycle ----------------------------------------------------------

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        for closer in reversed(self._closers):
            try:
                await closer()
            except Exception as exc:
                log.warning("di.close_error", closer=str(closer), exc=str(exc))
        self._registry_instances.clear()

    async def __aenter__(self) -> Container:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()


def _make_closer(container: Container, abstract: type, fn: Callable[[Any], Awaitable[None]]) -> Callable[[], Awaitable[None]]:
    async def closer() -> None:
        instance = container._registry_instances.get(abstract)
        if instance is not None:
            await fn(instance)

    return closer


def build_default_container() -> Container:
    """Build the production / default container with real adapters."""
    from datetime import datetime

    from noesis.config import get_settings
    from noesis.core import ports
    from noesis.kernel import Kernel

    container = Container()

    # Clock & IdGen — tiny no-deps ports default to real implementations.
    class _UtcClock:
        def now(self) -> datetime:
            return datetime.now(UTC)

    class _UUID4Gen:
        def new(self):  # type: ignore[no-untyped-def]
            return uuid4()

    container.register(ports.ClockPort, lambda _c: _UtcClock())
    container.register(ports.IdGenPort, lambda _c: _UUID4Gen())

    # Kernel — single-instance microkernel.
    async def _kernel_factory(c: Container) -> Kernel:
        from noesis.database.sql_repos import (
            SqlArtifactRepository,
            SqlConversationRepository,
            SqlDocumentRepository,
            SqlKnowledgeObjectRepository,
            SqlMemoryRepository,
            SqlMessageRepository,
            SqlTaskExecutionRepository,
            SqlUserRepository,
        )

        k = Kernel.build_default()
        # Wire repository adapters into Kernel's syscall handler context so
        # MEMORY_READ / CONVERSATION_CREATE / etc. actually persist.
        k._services["users"] = SqlUserRepository()
        k._services["conversations"] = SqlConversationRepository()
        k._services["messages"] = SqlMessageRepository()
        k._services["memories"] = SqlMemoryRepository()
        k._services["documents"] = SqlDocumentRepository()
        k._services["task_executions"] = SqlTaskExecutionRepository()
        k._services["artifacts"] = SqlArtifactRepository()
        k._services["knowledge_objects"] = SqlKnowledgeObjectRepository()
        return k

    async def _kernel_close(k: Kernel) -> None:
        await k.stop()

    container.register(Kernel, _kernel_factory, on_close=_kernel_close)

    # Chat + Embedding — defer to the factory.  These are lazy because
    # developers without API keys should still be able to run `noesis doctor`.
    async def _chat_factory(_c: Container) -> ports.ChatPort:
        from noesis.llm import get_provider

        return get_provider()  # type: ignore[return-value]

    async def _embedding_factory(_c: Container) -> ports.EmbeddingPort:
        from noesis.llm import get_embedding_provider

        return get_embedding_provider()  # type: ignore[return-value]

    container.register(ports.ChatPort, _chat_factory)
    container.register(ports.EmbeddingPort, _embedding_factory)

    # Repository ports — surface individually for callers that inject
    # repositories directly (API routes, plugins).  Same singletons the Kernel
    # holds, so writes in handlers are visible to route handlers.
    async def _user_repo(c: Container) -> ports.UserRepositoryPort:
        k = await c.get(Kernel)
        return k._services["users"]  # type: ignore[no-any-return]

    async def _conv_repo(c: Container) -> ports.ConversationRepositoryPort:
        k = await c.get(Kernel)
        return k._services["conversations"]  # type: ignore[no-any-return]

    async def _msg_repo(c: Container) -> ports.MessageRepositoryPort:
        k = await c.get(Kernel)
        return k._services["messages"]  # type: ignore[no-any-return]

    async def _mem_repo(c: Container) -> ports.MemoryRepositoryPort:
        k = await c.get(Kernel)
        return k._services["memories"]  # type: ignore[no-any-return]

    async def _doc_repo(c: Container) -> ports.DocumentRepositoryPort:
        k = await c.get(Kernel)
        return k._services["documents"]  # type: ignore[no-any-return]

    async def _te_repo(c: Container) -> ports.TaskExecutionRepositoryPort:
        k = await c.get(Kernel)
        return k._services["task_executions"]  # type: ignore[no-any-return]

    async def _art_repo(c: Container) -> ports.ArtifactRepositoryPort:
        k = await c.get(Kernel)
        return k._services["artifacts"]  # type: ignore[no-any-return]

    async def _ko_repo(c: Container) -> ports.KnowledgeObjectRepositoryPort:
        k = await c.get(Kernel)
        return k._services["knowledge_objects"]  # type: ignore[no-any-return]

    container.register(ports.UserRepositoryPort, _user_repo)
    container.register(ports.ConversationRepositoryPort, _conv_repo)
    container.register(ports.MessageRepositoryPort, _msg_repo)
    container.register(ports.MemoryRepositoryPort, _mem_repo)
    container.register(ports.DocumentRepositoryPort, _doc_repo)
    container.register(ports.TaskExecutionRepositoryPort, _te_repo)
    container.register(ports.ArtifactRepositoryPort, _art_repo)
    container.register(ports.KnowledgeObjectRepositoryPort, _ko_repo)

    # Settings — convenience singleton for routes that still need it.
    container.register(get_settings().__class__, lambda _c: get_settings())

    return container


__all__ = ["Container", "build_default_container"]
