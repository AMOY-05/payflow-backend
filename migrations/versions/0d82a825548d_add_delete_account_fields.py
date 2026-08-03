"""add delete account fields

Revision ID: 0d82a825548d
Revises: 9882801fcb9e
Create Date: 2026-07-07 00:10:26.602424

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0d82a825548d'
down_revision: Union[str, None] = '9882801fcb9e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add only the missing column to the users table
    op.add_column('users', sa.Column('is_email_verified', sa.Boolean(), server_default=sa.text('false'), nullable=False))


def downgrade() -> None:
    # Drop only the added column if rolling back
    op.drop_column('users', 'is_email_verified')