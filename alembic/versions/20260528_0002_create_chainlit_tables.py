"""create chainlit persistence tables

Revision ID: 20260528_0002
Revises: 20260528_0001
Create Date: 2026-05-28 00:02:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260528_0002"
down_revision = "20260528_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "User",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("identifier", sa.String(length=255), nullable=False),
        sa.Column(
            "metadata",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "createdAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updatedAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_chainlit_user_identifier", "User", ["identifier"], unique=True)

    op.create_table(
        "Thread",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("userId", sa.String(length=36), nullable=True),
        sa.Column(
            "metadata",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "tags",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "createdAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updatedAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("deletedAt", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["userId"], ["User.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_chainlit_thread_user_id", "Thread", ["userId"], unique=False)
    op.create_index(
        "ix_chainlit_thread_updated_at",
        "Thread",
        ["updatedAt"],
        unique=False,
    )

    op.create_table(
        "Step",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("threadId", sa.String(length=255), nullable=True),
        sa.Column("parentId", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("input", sa.Text(), nullable=True),
        sa.Column("output", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("showInput", sa.String(length=32), nullable=True),
        sa.Column(
            "isError",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "createdAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("startTime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("endTime", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["threadId"], ["Thread.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parentId"], ["Step.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_chainlit_step_thread_id", "Step", ["threadId"], unique=False)
    op.create_index("ix_chainlit_step_parent_id", "Step", ["parentId"], unique=False)

    op.create_table(
        "Element",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("threadId", sa.String(length=255), nullable=True),
        sa.Column("stepId", sa.String(length=255), nullable=True),
        sa.Column("chainlitKey", sa.String(length=255), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("objectKey", sa.Text(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("display", sa.String(length=32), nullable=False),
        sa.Column("mime", sa.String(length=255), nullable=True),
        sa.Column("size", sa.String(length=32), nullable=True),
        sa.Column("language", sa.String(length=32), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("autoPlay", sa.Boolean(), nullable=True),
        sa.Column("playerConfig", sa.JSON(), nullable=True),
        sa.Column(
            "metadata",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "props",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.ForeignKeyConstraint(["threadId"], ["Thread.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stepId"], ["Step.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_chainlit_element_thread_id",
        "Element",
        ["threadId"],
        unique=False,
    )
    op.create_index("ix_chainlit_element_step_id", "Element", ["stepId"], unique=False)

    op.create_table(
        "Feedback",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("stepId", sa.String(length=255), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["stepId"], ["Step.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_chainlit_feedback_step_id",
        "Feedback",
        ["stepId"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_chainlit_feedback_step_id", table_name="Feedback")
    op.drop_table("Feedback")
    op.drop_index("ix_chainlit_element_step_id", table_name="Element")
    op.drop_index("ix_chainlit_element_thread_id", table_name="Element")
    op.drop_table("Element")
    op.drop_index("ix_chainlit_step_parent_id", table_name="Step")
    op.drop_index("ix_chainlit_step_thread_id", table_name="Step")
    op.drop_table("Step")
    op.drop_index("ix_chainlit_thread_updated_at", table_name="Thread")
    op.drop_index("ix_chainlit_thread_user_id", table_name="Thread")
    op.drop_table("Thread")
    op.drop_index("ix_chainlit_user_identifier", table_name="User")
    op.drop_table("User")
