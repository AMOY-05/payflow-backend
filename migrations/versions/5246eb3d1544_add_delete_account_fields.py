"""add delete account fields

Revision ID: 5246eb3d1544
Revises: fee4a9b204ac
Create Date: 2026-07-06

"""
from alembic import op
import sqlalchemy as sa

revision = '5246eb3d1544'
down_revision = 'fee4a9b204ac'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_deleted with server_default so existing rows get False
    op.add_column('users', sa.Column(
        'is_deleted',
        sa.Boolean(),
        nullable=False,
        server_default='false'
    ))
    # Add deleted_at as nullable — no default needed
    op.add_column('users', sa.Column(
        'deleted_at',
        sa.DateTime(timezone=True),
        nullable=True
    ))


def downgrade() -> None:
    op.drop_column('users', 'deleted_at')
    op.drop_column('users', 'is_deleted')