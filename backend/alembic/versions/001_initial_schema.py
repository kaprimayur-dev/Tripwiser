"""initial schema setup with postgis and uuid extensions

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-09-23 16:58:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable PostGIS and UUID extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')

    # 2. Create stations table
    op.create_table(
        'stations',
        sa.Column('code', sa.String(length=10), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=True),
        sa.Column('zone', sa.String(length=10), nullable=True),
        sa.Column('location', geoalchemy2.types.Geography(geometry_type='POINT', srid=4326, from_text='ST_GeogFromText', name='geography', nullable=False), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('code')
    )

    # 3. Create trains table
    op.create_table(
        'trains',
        sa.Column('number', sa.String(length=10), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('origin_code', sa.String(length=10), nullable=False),
        sa.Column('destination_code', sa.String(length=10), nullable=False),
        sa.Column('runs_on_days', postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['origin_code'], ['stations.code'], ),
        sa.ForeignKeyConstraint(['destination_code'], ['stations.code'], ),
        sa.PrimaryKeyConstraint('number')
    )

    # 4. Create train_schedules table
    op.create_table(
        'train_schedules',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('train_number', sa.String(length=10), nullable=False),
        sa.Column('station_code', sa.String(length=10), nullable=False),
        sa.Column('stop_sequence', sa.Integer(), nullable=False),
        sa.Column('arrival_time', sa.Time(), nullable=True),
        sa.Column('departure_time', sa.Time(), nullable=True),
        sa.Column('day_offset', sa.Integer(), server_default='0', nullable=False),
        sa.Column('distance_km', sa.Numeric(precision=7, scale=2), server_default='0.0', nullable=False),
        sa.ForeignKeyConstraint(['station_code'], ['stations.code'], ),
        sa.ForeignKeyConstraint(['train_number'], ['trains.number'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('train_number', 'stop_sequence', name='uq_train_stop_sequence')
    )
    op.create_index('idx_schedules_lookup', 'train_schedules', ['station_code', 'train_number'], unique=False)

    # 5. Create chart_vacancies table
    op.create_table(
        'chart_vacancies',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('train_number', sa.String(length=10), nullable=False),
        sa.Column('chart_date', sa.Date(), nullable=False),
        sa.Column('coach', sa.String(length=10), nullable=False),
        sa.Column('berth_number', sa.Integer(), nullable=False),
        sa.Column('berth_type', sa.String(length=10), server_default='UB', nullable=False),
        sa.Column('travel_class', sa.String(length=10), nullable=False),
        sa.Column('from_station_code', sa.String(length=10), nullable=False),
        sa.Column('to_station_code', sa.String(length=10), nullable=False),
        sa.Column('from_sequence', sa.Integer(), nullable=False),
        sa.Column('to_sequence', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=50), server_default='chart_feed', nullable=False),
        sa.Column('chart_phase', sa.String(length=50), server_default='FIRST_CHART', nullable=False),
        sa.Column('status', sa.String(length=20), server_default='VACANT', nullable=False),
        sa.Column('observed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['from_station_code'], ['stations.code'], ),
        sa.ForeignKeyConstraint(['to_station_code'], ['stations.code'], ),
        sa.ForeignKeyConstraint(['train_number'], ['trains.number'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_vacancies_search', 'chart_vacancies', ['train_number', 'chart_date', 'from_sequence', 'to_sequence', 'status'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_vacancies_search', table_name='chart_vacancies')
    op.drop_table('chart_vacancies')
    
    op.drop_index('idx_schedules_lookup', table_name='train_schedules')
    op.drop_table('train_schedules')
    
    op.drop_table('trains')
    op.drop_table('stations')
