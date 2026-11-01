"""add unique constraint to chart_vacancies for segment deduplication

Revision ID: 002_chart_vacancies_unique
Revises: 001_initial_schema
Create Date: 2026-11-01 22:15:00.000000

"""
from typing import Sequence, Union
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '002_chart_vacancies_unique'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        'uq_chart_vacancies_segment',
        'chart_vacancies',
        ['train_number', 'chart_date', 'coach', 'berth_number', 'from_sequence', 'to_sequence']
    )


def downgrade() -> None:
    op.drop_constraint(
        'uq_chart_vacancies_segment',
        'chart_vacancies',
        type_='unique'
    )

