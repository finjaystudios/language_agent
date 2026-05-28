"""convert chainlit persistence columns from json to jsonb

Revision ID: 20260528_0003
Revises: 20260528_0002
Create Date: 2026-05-28 17:20:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260528_0003"
down_revision = "20260528_0002"
branch_labels = None
depends_on = None


def _jsonb() -> postgresql.JSONB:
    return postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.alter_column(
        "User",
        "metadata",
        type_=_jsonb(),
        existing_type=sa.JSON(),
        existing_nullable=False,
        existing_server_default=sa.text("'{}'"),
        server_default=sa.text("'{}'::jsonb"),
        postgresql_using='"metadata"::jsonb',
    )
    op.alter_column(
        "Thread",
        "metadata",
        type_=_jsonb(),
        existing_type=sa.JSON(),
        existing_nullable=False,
        existing_server_default=sa.text("'{}'"),
        server_default=sa.text("'{}'::jsonb"),
        postgresql_using='"metadata"::jsonb',
    )
    op.alter_column(
        "Thread",
        "tags",
        type_=_jsonb(),
        existing_type=sa.JSON(),
        existing_nullable=False,
        existing_server_default=sa.text("'[]'"),
        server_default=sa.text("'[]'::jsonb"),
        postgresql_using='"tags"::jsonb',
    )
    op.alter_column(
        "Step",
        "metadata",
        type_=_jsonb(),
        existing_type=sa.JSON(),
        existing_nullable=False,
        existing_server_default=sa.text("'{}'"),
        server_default=sa.text("'{}'::jsonb"),
        postgresql_using='"metadata"::jsonb',
    )
    op.alter_column(
        "Element",
        "playerConfig",
        type_=_jsonb(),
        existing_type=sa.JSON(),
        existing_nullable=True,
        postgresql_using='"playerConfig"::jsonb',
    )
    op.alter_column(
        "Element",
        "metadata",
        type_=_jsonb(),
        existing_type=sa.JSON(),
        existing_nullable=False,
        existing_server_default=sa.text("'{}'"),
        server_default=sa.text("'{}'::jsonb"),
        postgresql_using='"metadata"::jsonb',
    )
    op.alter_column(
        "Element",
        "props",
        type_=_jsonb(),
        existing_type=sa.JSON(),
        existing_nullable=False,
        existing_server_default=sa.text("'{}'"),
        server_default=sa.text("'{}'::jsonb"),
        postgresql_using='"props"::jsonb',
    )


def downgrade() -> None:
    op.alter_column(
        "Element",
        "props",
        type_=sa.JSON(),
        existing_type=_jsonb(),
        existing_nullable=False,
        existing_server_default=sa.text("'{}'::jsonb"),
        server_default=sa.text("'{}'"),
        postgresql_using='"props"::json',
    )
    op.alter_column(
        "Element",
        "metadata",
        type_=sa.JSON(),
        existing_type=_jsonb(),
        existing_nullable=False,
        existing_server_default=sa.text("'{}'::jsonb"),
        server_default=sa.text("'{}'"),
        postgresql_using='"metadata"::json',
    )
    op.alter_column(
        "Element",
        "playerConfig",
        type_=sa.JSON(),
        existing_type=_jsonb(),
        existing_nullable=True,
        postgresql_using='"playerConfig"::json',
    )
    op.alter_column(
        "Step",
        "metadata",
        type_=sa.JSON(),
        existing_type=_jsonb(),
        existing_nullable=False,
        existing_server_default=sa.text("'{}'::jsonb"),
        server_default=sa.text("'{}'"),
        postgresql_using='"metadata"::json',
    )
    op.alter_column(
        "Thread",
        "tags",
        type_=sa.JSON(),
        existing_type=_jsonb(),
        existing_nullable=False,
        existing_server_default=sa.text("'[]'::jsonb"),
        server_default=sa.text("'[]'"),
        postgresql_using='"tags"::json',
    )
    op.alter_column(
        "Thread",
        "metadata",
        type_=sa.JSON(),
        existing_type=_jsonb(),
        existing_nullable=False,
        existing_server_default=sa.text("'{}'::jsonb"),
        server_default=sa.text("'{}'"),
        postgresql_using='"metadata"::json',
    )
    op.alter_column(
        "User",
        "metadata",
        type_=sa.JSON(),
        existing_type=_jsonb(),
        existing_nullable=False,
        existing_server_default=sa.text("'{}'::jsonb"),
        server_default=sa.text("'{}'"),
        postgresql_using='"metadata"::json',
    )
