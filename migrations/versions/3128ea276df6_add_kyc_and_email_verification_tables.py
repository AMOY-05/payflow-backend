"""add kyc and email verification tables

Revision ID: 3128ea276df6
Revises: deb365af6b8c
Create Date: 2026-07-07 08:29:39.165044

"""
"""add kyc and email verification tables

Revision ID: 3128ea276df6
Revises: deb365af6b8c
Create Date: 2026-07-07 00:10:26.602424

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3128ea276df6'
down_revision: Union[str, None] = 'deb365af6b8c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # These tables were already created in migration 9882801fcb9e
    pass


def downgrade() -> None:
    pass