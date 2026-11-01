"""
Batch persistence service for high-volume railway entities in PostgreSQL/PostGIS.

Provides chunked, idempotent bulk upserts for stations, trains, and train schedules,
enforcing foreign key ordering, transactional integrity, and parameter bounds.
"""

from typing import Sequence, Tuple, Optional
import logging
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal
from app.domain.models.station import Station
from app.domain.models.train import Train
from app.infrastructure.database.models.station import StationORM
from app.infrastructure.database.models.train import TrainORM, ScheduleORM
from app.infrastructure.integration.models import IntegratedRailwayDataset

logger = logging.getLogger(__name__)


class RailwayDataPersistenceService:
    """
    High-throughput, idempotent batch persistence service for railway network datasets.
    """

    def __init__(self, default_session_factory=AsyncSessionLocal) -> None:
        self.session_factory = default_session_factory

    async def bulk_upsert_stations(
        self,
        stations: Sequence[Station],
        chunk_size: int = 1000,
        session: Optional[AsyncSession] = None,
    ) -> int:
        """
        Bulk upsert stations in chunks using PostgreSQL ON CONFLICT DO UPDATE.
        
        Args:
            stations: Sequence of Station domain entities.
            chunk_size: Maximum rows per SQL INSERT statement (must stay within driver limits).
            session: Optional existing AsyncSession. If omitted, a new session is opened and committed.

        Returns:
            Number of stations processed.
        """
        if not stations:
            return 0

        if session is not None:
            return await self._execute_bulk_stations(stations, chunk_size, session)

        async with self.session_factory() as s:
            async with s.begin():
                count = await self._execute_bulk_stations(stations, chunk_size, s)
            return count

    async def _execute_bulk_stations(
        self,
        stations: Sequence[Station],
        chunk_size: int,
        session: AsyncSession,
    ) -> int:
        total = len(stations)
        for i in range(0, total, chunk_size):
            chunk = stations[i : i + chunk_size]
            values = [
                {
                    "code": s.code,
                    "name": s.name,
                    "city": s.city,
                    "state": s.state,
                    "zone": s.zone,
                    "location": f"SRID=4326;POINT({s.longitude} {s.latitude})",
                }
                for s in chunk
            ]
            stmt = pg_insert(StationORM).values(values)
            stmt = stmt.on_conflict_do_update(
                index_elements=[StationORM.code],
                set_={
                    "name": stmt.excluded.name,
                    "city": stmt.excluded.city,
                    "state": stmt.excluded.state,
                    "zone": stmt.excluded.zone,
                    "location": stmt.excluded.location,
                },
            )
            await session.execute(stmt)

        logger.info("Successfully bulk upserted %d stations in chunks of %d", total, chunk_size)
        return total

    async def bulk_upsert_trains(
        self,
        trains: Sequence[Train],
        chunk_size: int = 500,
        session: Optional[AsyncSession] = None,
    ) -> int:
        """
        Bulk upsert compiled domain trains and their complete schedules.
        
        Schedules are updated transactionally per chunk: existing child schedules are
        purged and fresh deterministic schedules inserted to avoid orphaned stops.

        Args:
            trains: Sequence of validated domain Train entities.
            chunk_size: Number of trains to process per batch.
            session: Optional existing AsyncSession. If omitted, a new session is opened and committed.

        Returns:
            Number of trains processed.
        """
        if not trains:
            return 0

        if session is not None:
            return await self._execute_bulk_trains(trains, chunk_size, session)

        async with self.session_factory() as s:
            async with s.begin():
                count = await self._execute_bulk_trains(trains, chunk_size, s)
            return count

    async def _execute_bulk_trains(
        self,
        trains: Sequence[Train],
        chunk_size: int,
        session: AsyncSession,
    ) -> int:
        total = len(trains)
        for i in range(0, total, chunk_size):
            chunk = trains[i : i + chunk_size]
            train_numbers = [t.number for t in chunk]

            # 1. Upsert Train headers
            train_values = [
                {
                    "number": t.number,
                    "name": t.name,
                    "origin_code": t.origin_code,
                    "destination_code": t.destination_code,
                    "runs_on_days": list(t.runs_on_days),
                }
                for t in chunk
            ]
            stmt_train = pg_insert(TrainORM).values(train_values)
            stmt_train = stmt_train.on_conflict_do_update(
                index_elements=[TrainORM.number],
                set_={
                    "name": stmt_train.excluded.name,
                    "origin_code": stmt_train.excluded.origin_code,
                    "destination_code": stmt_train.excluded.destination_code,
                    "runs_on_days": stmt_train.excluded.runs_on_days,
                },
            )
            await session.execute(stmt_train)

            # 2. Clear old schedules for the current chunk of trains
            await session.execute(
                delete(ScheduleORM).where(ScheduleORM.train_number.in_(train_numbers))
            )

            # 3. Construct uniform schedule rows
            schedule_values = []
            for t in chunk:
                for entry in t.schedule:
                    schedule_values.append(
                        {
                            "train_number": t.number,
                            "station_code": entry.station_code,
                            "stop_sequence": entry.stop_sequence,
                            "arrival_time": entry.arrival_time,
                            "departure_time": entry.departure_time,
                            "day_offset": entry.day_offset,
                            "distance_km": float(entry.distance_km),
                        }
                    )

            # 4. Insert schedules in slices of 1,000 to keep parameter count well below 65,535
            if schedule_values:
                sch_chunk_size = 1000
                for j in range(0, len(schedule_values), sch_chunk_size):
                    sch_slice = schedule_values[j : j + sch_chunk_size]
                    stmt_sch = pg_insert(ScheduleORM).values(sch_slice)
                    await session.execute(stmt_sch)

        logger.info("Successfully bulk upserted %d trains with schedules in chunks of %d", total, chunk_size)
        return total

    async def persist_dataset(
        self,
        dataset: IntegratedRailwayDataset,
        persist_stations: bool = True,
        persist_trains: bool = True,
        chunk_size: int = 1000,
        session: Optional[AsyncSession] = None,
    ) -> Tuple[int, int]:
        """
        Coordinates full dataset persistence adhering to foreign-key constraints.
        
        Stations are persisted first, followed by Tier 2 compiled domain trains.
        Non-qualifying trains are not persisted into the database.

        Returns:
            Tuple of (stations_upserted_count, trains_upserted_count).
        """
        st_count = 0
        tr_count = 0

        if session is not None:
            if persist_stations and dataset.stations:
                st_count = await self._execute_bulk_stations(dataset.stations, chunk_size, session)
            if persist_trains and dataset.compiled_trains:
                valid_numbers = [t.number for t in dataset.compiled_trains]
                await session.execute(
                    delete(TrainORM).where(TrainORM.number.not_in(valid_numbers))
                )
                tr_count = await self._execute_bulk_trains(dataset.compiled_trains, chunk_size, session)
            return st_count, tr_count

        async with self.session_factory() as s:
            async with s.begin():
                if persist_stations and dataset.stations:
                    st_count = await self._execute_bulk_stations(dataset.stations, chunk_size, s)
                if persist_trains and dataset.compiled_trains:
                    valid_numbers = [t.number for t in dataset.compiled_trains]
                    await s.execute(
                        delete(TrainORM).where(TrainORM.number.not_in(valid_numbers))
                    )
                    tr_count = await self._execute_bulk_trains(dataset.compiled_trains, chunk_size, s)

        return st_count, tr_count

