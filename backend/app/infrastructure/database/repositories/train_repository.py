from typing import Optional, List, Tuple, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func, case, exists
from sqlalchemy.orm import selectinload, aliased
from app.domain.repositories.train_repository import TrainRepository
from app.domain.models.train import Train, TrainScheduleEntry
from app.infrastructure.database.models.train import TrainORM, ScheduleORM
from app.infrastructure.database.models.station import StationORM

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

    async def search_trains(self, query: str, limit: int = 15) -> List[TrainORM]:
        clean_q = query.strip()
        if not clean_q:
            return []
        pattern = f"%{clean_q}%"

        # Correlated EXISTS subquery for intermediate station matching without in-memory schedule aggregation
        calling_station_exists = exists(
            select(1)
            .select_from(ScheduleORM)
            .join(StationORM, ScheduleORM.station_code == StationORM.code)
            .where(
                ScheduleORM.train_number == TrainORM.number,
                or_(
                    StationORM.code.ilike(f"{clean_q}%"),
                    StationORM.name.ilike(pattern),
                ),
            )
        )

        stmt = (
            select(TrainORM)
            .options(selectinload(TrainORM.schedules))
            .where(
                or_(
                    TrainORM.number.ilike(f"{clean_q}%"),
                    TrainORM.name.ilike(pattern),
                    TrainORM.origin_code.ilike(f"{clean_q}%"),
                    TrainORM.destination_code.ilike(f"{clean_q}%"),
                    calling_station_exists,
                )
            )
            .order_by(
                case(
                    (TrainORM.number == clean_q, 1),
                    (TrainORM.number.ilike(f"{clean_q}%"), 2),
                    (TrainORM.name.ilike(pattern), 3),
                    else_=4,
                ),
                TrainORM.number,
            )
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_trains_serving_station(
        self, station_code: str, limit: int = 100
    ) -> List[Tuple[TrainORM, ScheduleORM, int, int, int]]:
        """
        Retrieves all trains scheduled to stop at, originate from, or terminate at station_code.
        Returns list of (TrainORM, ScheduleORM for this stop occurrence, min_seq, max_seq, total_stops).
        Preserves multiple visits to the same station by a single train (e.g. loops or reversal junctions).
        Sorts scheduled departure/arrival times using NULLS LAST to prevent missing times from acting as midnight.
        """
        clean_code = station_code.strip().upper()

        seq_subq = (
            select(
                ScheduleORM.train_number,
                func.min(ScheduleORM.stop_sequence).label("min_seq"),
                func.max(ScheduleORM.stop_sequence).label("max_seq"),
                func.count(ScheduleORM.stop_sequence).label("total_stops"),
            )
            .group_by(ScheduleORM.train_number)
            .subquery()
        )

        stmt = (
            select(
                TrainORM,
                ScheduleORM,
                seq_subq.c.min_seq,
                seq_subq.c.max_seq,
                seq_subq.c.total_stops,
            )
            .options(selectinload(TrainORM.schedules))
            .join(ScheduleORM, TrainORM.number == ScheduleORM.train_number)
            .join(seq_subq, TrainORM.number == seq_subq.c.train_number)
            .where(ScheduleORM.station_code == clean_code)
            .order_by(
                case(
                    (ScheduleORM.departure_time.isnot(None), ScheduleORM.departure_time),
                    else_=ScheduleORM.arrival_time,
                ).asc().nulls_last(),
                ScheduleORM.stop_sequence.asc(),
                TrainORM.number.asc(),
            )
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.all())

    async def compare_direct_trains(
        self, origin_code: str, destination_code: str
    ) -> List[Tuple[TrainORM, ScheduleORM, ScheduleORM]]:
        """
        Finds all direct trains where origin_code appears before destination_code in the schedule sequence.
        For trains with multiple visits to either station, deterministically selects the valid forward segment
        with the minimal sequence span, tie-broken by earliest origin sequence.
        Returns deduplicated list of tuples: (TrainORM, exact_selected_orig_schedule, exact_selected_dest_schedule)
        """
        orig_clean = origin_code.strip().upper()
        dest_clean = destination_code.strip().upper()

        orig_sched = aliased(ScheduleORM)
        dest_sched = aliased(ScheduleORM)

        stmt = (
            select(TrainORM, orig_sched, dest_sched)
            .options(selectinload(TrainORM.schedules))
            .join(
                orig_sched,
                (TrainORM.number == orig_sched.train_number) & (orig_sched.station_code == orig_clean),
            )
            .join(
                dest_sched,
                (TrainORM.number == dest_sched.train_number) & (dest_sched.station_code == dest_clean),
            )
            .where(orig_sched.stop_sequence < dest_sched.stop_sequence)
        )
        result = await self.session.execute(stmt)
        raw_rows = list(result.all())

        # Deterministic deduplication by train number:
        # Group by train_number, selecting the segment with minimal sequence span (dest_seq - orig_seq)
        # and earliest orig_seq as tie-breaker.
        best_per_train: Dict[str, Tuple[TrainORM, ScheduleORM, ScheduleORM]] = {}
        for train, orig_s, dest_s in raw_rows:
            num = train.number
            current_span = dest_s.stop_sequence - orig_s.stop_sequence
            if num not in best_per_train:
                best_per_train[num] = (train, orig_s, dest_s)
            else:
                _, prev_orig, prev_dest = best_per_train[num]
                prev_span = prev_dest.stop_sequence - prev_orig.stop_sequence
                if (current_span, orig_s.stop_sequence) < (prev_span, prev_orig.stop_sequence):
                    best_per_train[num] = (train, orig_s, dest_s)

        # Sort deduplicated list by departure time NULLS LAST, then train number
        deduped = list(best_per_train.values())

        def sort_key(row):
            t, o, _ = row
            dep = o.departure_time or o.arrival_time
            # Return tuple for sorting: (has_time: 0 if present else 1, time_str, train_number)
            if dep is not None:
                return (0, dep.isoformat(), t.number)
            return (1, "99:99:99", t.number)

        deduped.sort(key=sort_key)
        return deduped

    async def get_schedule_with_stations(self, train_number: str) -> List[Tuple[ScheduleORM, str]]:
        stmt = (
            select(ScheduleORM, StationORM.name.label("station_name"))
            .join(StationORM, ScheduleORM.station_code == StationORM.code)
            .where(ScheduleORM.train_number == train_number.strip())
            .order_by(ScheduleORM.stop_sequence)
        )
        result = await self.session.execute(stmt)
        return list(result.all())

    async def get_station_names_for_codes(self, station_codes: List[str]) -> Dict[str, str]:
        if not station_codes:
            return {}
        stmt = select(StationORM.code, StationORM.name).where(StationORM.code.in_(station_codes))
        result = await self.session.execute(stmt)
        return {code: name for code, name in result.all()}

