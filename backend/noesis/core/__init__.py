"""
``astra.core`` — domain layer (no IO, no external deps beyond stdlib + pydantic).

Follows hexagonal architecture conventions:
  * ``ports`` — abstract interfaces for every driven side
  * ``services`` — pure use-case orchestrators (import ports only, never adapters)
  * ``di`` — dependency-injection container (wires concrete adapters into ports)
  * ``events`` — canonical domain event names
  * ``domain`` — domain-value-object primitives (ValueObject, Entity, etc.)

Rules enforced in this package:
    1. No module under ``astra.core`` may import from ``astra.llm``,
       ``astra.database``, ``astra.api``, or any HTTP library.
    2. The only imports allowed from outside ``astra`` are stdlib and
       ``astra.types`` (Pydantic models are DTOs shared across boundaries).
"""

__all__ = ["ports"]
