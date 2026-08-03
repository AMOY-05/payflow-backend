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
    # Everything in this step was already created in prior migrations
    pass


def downgrade() -> None:
    pass