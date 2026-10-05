"""
Test-support package.

Reusable fixtures, in-memory repository implementations, and fake
LLM/embedding providers live here. Nothing in ``noesis.*`` imports this
module — it's a test-only dependency (installed via pytest ``pythonpath``
in pyproject.toml).
"""
