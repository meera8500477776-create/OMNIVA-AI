"""Add durable Care Companion reminders.

Revision ID: b7c81f041e2a
Revises: a3b3cded9149
"""
from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "b7c81f041e2a"
down_revision: str | None = "a3b3cded9149"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "carereminder",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(length=120), nullable=False),
        sa.Column("body", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=False),
        sa.Column("reminder_type", sqlmodel.sql.sqltypes.AutoString(length=30), nullable=False),
        sa.Column("scheduled_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.Column("timezone_name", sqlmodel.sql.sqltypes.AutoString(length=80), nullable=False),
        sa.Column("quiet_start", sqlmodel.sql.sqltypes.AutoString(length=5), nullable=False),
        sa.Column("quiet_end", sqlmodel.sql.sqltypes.AutoString(length=5), nullable=False),
        sa.Column("idempotency_key", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("fired_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True),
        sa.Column("acknowledged_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True),
        sa.Column("push_status", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("push_attempted_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True),
        sa.Column("created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_care_reminder_user_key"),
    )
    with op.batch_alter_table("carereminder") as batch:
        batch.create_index("ix_carereminder_user_id", ["user_id"])
        batch.create_index("ix_carereminder_scheduled_at", ["scheduled_at"])
        batch.create_index("ix_carereminder_status", ["status"])


def downgrade() -> None:
    with op.batch_alter_table("carereminder") as batch:
        batch.drop_index("ix_carereminder_status")
        batch.drop_index("ix_carereminder_scheduled_at")
        batch.drop_index("ix_carereminder_user_id")
    op.drop_table("carereminder")
