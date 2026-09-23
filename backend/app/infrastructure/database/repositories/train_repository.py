from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.domain.repositories.train_repository import TrainRepository
from app.domain.models.train import Train, TrainScheduleEntry
from app.infrastructure.database.models.train import TrainORM, ScheduleORM

class SQLAlchemyTrainRepository(TrainRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_domain(self, orm: TrainORM) -> Train:
        schedules = [
            TrainScheduleEntry(
                station_code=s.station_code,
                arrival_time=s.arrival_time,
                departure_time=s.departure_time,
                day_offset=s.day_offset,
                distance_km=float(s.distance_km),
                stop_sequence=s.stop_sequence
            )
            for s in sorted(orm.schedules, key=lambda x: x.stop_sequence)
        ]
        return Train(
            number=orm.number,
            name=orm.name,
            origin_code=orm.origin_code,
            destination_code=orm.destination_code,
            runs_on_days=list(orm.runs_on_days),
            schedule=schedules
        )

    async def get_by_number(self, train_number: str) -> Optional[Train]:
        stmt = (
            select(TrainORM)
            .options(selectinload(TrainORM.schedules))
            .where(TrainORM.number == train_number)
        )
        result = await self.session.execute(stmt)
        orm = result.scalar_one_or_none()
        if not orm:
            return None
        return self._to_domain(orm)

    async def find_direct_trains(self, origin_code: str, destination_code: str) -> list[Train]:
        # Subquery or join to find trains where origin sequence < destination sequence
        s1 = select(ScheduleORM.train_number, ScheduleORM.stop_sequence.label("seq_orig")).where(ScheduleORM.station_code == origin_code).subquery()
        s2 = select(ScheduleORM.train_number, ScheduleORM.stop_sequence.label("seq_dest")).where(ScheduleORM.station_code == destination_code).subquery()
        
        stmt = (
            select(TrainORM)
            .join(s1, TrainORM.number == s1.c.train_number)
            .join(s2, TrainORM.number == s2.c.train_number)
            .where(s1.c.seq_orig < s2.c.seq_dest)
            .options(selectinload(TrainORM.schedules))
        )
        result = await self.session.execute(stmt)
        return [self._to_domain(orm) for orm in result.scalars().all()]

    async def save(self, train: Train) -> Train:
        orm = await self.session.get(TrainORM, train.number)
        if not orm:
            orm = TrainORM(
                number=train.number,
                name=train.name,
                origin_code=train.origin_code,
                destination_code=train.destination_code,
                runs_on_days=train.runs_on_days
            )
            self.session.add(orm)
        else:
            orm.name = train.name
            orm.origin_code = train.origin_code
            orm.destination_code = train.destination_code
            orm.runs_on_days = train.runs_on_days
            # Clear existing schedules for full replacement
            stmt_del = select(ScheduleORM).where(ScheduleORM.train_number == train.number)
            res = await self.session.execute(stmt_del)
            for old_s in res.scalars().all():
                await self.session.delete(old_s)

        for entry in train.schedule:
            s_orm = ScheduleORM(
                train_number=train.number,
                station_code=entry.station_code,
                stop_sequence=entry.stop_sequence,
                arrival_time=entry.arrival_time,
                departure_time=entry.departure_time,
                day_offset=entry.day_offset,
                distance_km=entry.distance_km
            )
            self.session.add(s_orm)

        await self.session.flush()
        return train
