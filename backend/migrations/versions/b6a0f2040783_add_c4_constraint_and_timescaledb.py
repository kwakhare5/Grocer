"""Add C4 constraint and TimescaleDB hypertable

Revision ID: b6a0f2040783
Revises: a6a0f2040782
Create Date: 2026-07-08 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b6a0f2040783'
down_revision: Union[str, None] = 'a6a0f2040782'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add UniqueConstraint to consumption_models
    op.create_unique_constraint(
        'uq_consumption_model_household_item',
        'consumption_models',
        ['household_id', 'item_id']
    )

    # 2. Convert price_history to a TimescaleDB hypertable
    # Note: TimescaleDB extension must be created first if it doesn't exist
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")
    
    # Check if it's already a hypertable, if not, create it
    # We use a DO block to prevent errors if it's already a hypertable
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 
                FROM timescaledb_information.hypertables 
                WHERE hypertable_name = 'price_history'
            ) THEN
                PERFORM create_hypertable('price_history', 'recorded_at', if_not_exists => TRUE);
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    # 1. Drop the UniqueConstraint
    op.drop_constraint(
        'uq_consumption_model_household_item',
        'consumption_models',
        type_='unique'
    )
    
    # Note: Reverting a hypertable to a regular table is non-trivial and often involves creating 
    # a new table, copying data, and renaming. In many downgrade scenarios, we just leave the 
    # hypertable as is unless strictly required to drop it.
