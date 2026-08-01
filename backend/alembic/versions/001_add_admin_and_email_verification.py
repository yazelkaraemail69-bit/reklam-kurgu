"""Add admin and email verification columns to users table.

Revision ID: 001
Revises:
Create Date: 2026-08-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default="0"))
    op.create_index(op.f("ix_users_is_admin"), "users", ["is_admin"])


def downgrade() -> None:
    op.drop_index(op.f("ix_users_is_admin"), table_name="users")
    op.drop_column("users", "email_verified")
    op.drop_column("users", "is_admin")
