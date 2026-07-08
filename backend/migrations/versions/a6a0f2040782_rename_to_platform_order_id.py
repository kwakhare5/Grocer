"""rename_to_platform_order_id

Revision ID: a6a0f2040782
Revises: 36a0f2040781
Create Date: 2026-07-08 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a6a0f2040782'
down_revision: Union[str, Sequence[str], None] = '36a0f2040781'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename instamart_order_id to platform_order_id
    op.alter_column('orders', 'instamart_order_id', new_column_name='platform_order_id')
    # Add platform column with server default 'instamart'
    op.add_column('orders', sa.Column('platform', sa.String(length=50), nullable=False, server_default='instamart'))


def downgrade() -> None:
    # Remove platform column
    op.drop_column('orders', 'platform')
    # Rename platform_order_id back to instamart_order_id
    op.alter_column('orders', 'platform_order_id', new_column_name='instamart_order_id')
