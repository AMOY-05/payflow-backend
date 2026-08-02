"""add delete account fields

Revision ID: deb365af6b8c
Revises: 0d82a825548d
Create Date: 2026-07-06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = 'deb365af6b8c'
down_revision = '0d82a825548d'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    """Check if a column already exists in the table."""
    bind = op.get_bind()
    result = bind.execute(text(
        f"SELECT column_name FROM information_schema.columns "
        f"WHERE table_name='{table_name}' AND column_name='{column_name}'"
    ))
    return result.fetchone() is not None


def upgrade() -> None:
    if not column_exists('users', 'is_deleted'):
        op.add_column('users', sa.Column(
            'is_deleted',
            sa.Boolean(),
            nullable=False,
            server_default='false'
        ))

    if not column_exists('users', 'deleted_at'):
        op.add_column('users', sa.Column(
            'deleted_at',
            sa.DateTime(timezone=True),
            nullable=True
        ))

    if not column_exists('users', 'is_email_verified'):
        op.add_column('users', sa.Column(
            'is_email_verified',
            sa.Boolean(),
            nullable=False,
            server_default='false'
        ))


def downgrade() -> None:
    if column_exists('users', 'is_email_verified'):
        op.drop_column('users', 'is_email_verified')
    if column_exists('users', 'deleted_at'):
        op.drop_column('users', 'deleted_at')
    if column_exists('users', 'is_deleted'):
        op.drop_column('users', 'is_deleted')