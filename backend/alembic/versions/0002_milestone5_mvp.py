"""milestone5_kernel_mvp — revision stamp for M5 shipped state

Revision ID: 0002_milestone5_mvp
Revises: 0001_milestone0_schema
Create Date: 2026-08-03 00:00:00.000000

This migration is intentionally a no-op (no DDL).  Purpose:
  * Record in the Alembic `alembic_version` table that the schema
    has reached the "Milestone 5 Kernel MVP" state (which matches
    what SQLAlchemy `Base.metadata.create_all()` produces for
    `noesis.database.models.Base` as of M5 shipdate).
  * Existing deployments that bootstrapped via `create_all()` and
    have an empty `alembic_version` table can safely run
    `alembic stamp head` / `alembic upgrade head` and get a
    consistent revision marker *without* replaying any DDL that
    would drop/recreate data.
  * Future milestone migrations (Postgres auth columns, Qdrant
    collection stubs, rate-limit tables, etc.) can properly depend
    on this revision as their baseline, which makes them applicable
    on top of either `0001_milestone0_schema` migrations or
    `create_all()`-bootstrapped databases.

Upgrade / downgrade are both no-op so this revision is fully
reversible without data loss.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0002_milestone5_mvp"
down_revision: str | None = "0001_milestone0_schema"
branch_labels: str | Sequence[str] | None = ("milestone5",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Intentionally empty: just stamp the revision marker
    pass


def downgrade() -> None:
    # Intentionally empty: just pop the revision marker back to 0001
    pass
