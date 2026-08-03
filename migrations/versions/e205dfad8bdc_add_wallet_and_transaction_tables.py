"""add wallet and transaction tables

Revision ID: e205dfad8bdc
Revises: d47c165a9711
Create Date: 2026-07-01 09:45:46.846339

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    # Create the 'wallets' table
    op.create_table(
        'wallets',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('balance', sa.Numeric(precision=18, scale=2), server_default='0.00', nullable=False),
        sa.Column('currency', sa.String(), nullable=False, server_default='USD'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    # Delete the 'wallets' table if rolling back
    op.drop_table('wallets')
