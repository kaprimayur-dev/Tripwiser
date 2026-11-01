"""expand train number length to 20 to support full railway dataset

Revision ID: 003_expand_train_number_length
Revises: 002_chart_vacancies_unique
Create Date: 2026-11-01 22:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '003_expand_train_number_length'
down_revision: Union[str, None] = '002_chart_vacancies_unique'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'trains',
        'number',
        type_=sa.String(20),
        existing_type=sa.String(10),
        existing_nullable=False,
    )
    op.alter_column(
        'train_schedules',
        'train_number',
        type_=sa.String(20),
        existing_type=sa.String(10),
        existing_nullable=False,
    )
    op.alter_column(
        'chart_vacancies',
        'train_number',
        type_=sa.String(20),
        existing_type=sa.String(10),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        'chart_vacancies',
        'train_number',
        type_=sa.String(10),
        existing_type=sa.String(20),
        existing_nullable=False,
    )
    op.alter_column(
        'train_schedules',
        'train_number',
        type_=sa.String(10),
        existing_type=sa.String(20),
        existing_nullable=False,
    )
    op.alter_column(
        'trains',
        'number',
        type_=sa.String(10),
        existing_type=sa.String(20),
        existing_nullable=False,
    )
