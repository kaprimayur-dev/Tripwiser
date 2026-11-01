import datetime
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.bachelor import BerthSegment
from app.domain.repositories.vacancy_repository import VacancyRepository
from app.infrastructure.database.models.vacancy import ChartVacancyORM

class PostgresVacancyRepository(VacancyRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_vacancies_for_train(
        self,
        train_number: str,
        travel_date: datetime.date,
        min_seq: int,
        max_seq: int,
        travel_class: Optional[str] = None,
    ) -> list[BerthSegment]:
        """
        Retrieve active, unexpired vacant berth segments for a given train run,
        bounded by the journey stop sequences [min_seq, max_seq].
        """
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        stmt = (
            select(ChartVacancyORM)
            .where(
                ChartVacancyORM.train_number == train_number,
                ChartVacancyORM.chart_date == travel_date,
                ChartVacancyORM.status == "VACANT",
                ChartVacancyORM.expires_at > now_utc,
                ChartVacancyORM.from_sequence >= min_seq,
                ChartVacancyORM.to_sequence <= max_seq,
            )
            .order_by(
                ChartVacancyORM.from_sequence.asc(),
                ChartVacancyORM.to_sequence.asc(),
                ChartVacancyORM.coach.asc(),
                ChartVacancyORM.berth_number.asc(),
            )
        )

        if travel_class:
            stmt = stmt.where(ChartVacancyORM.travel_class == travel_class.upper())

        result = await self.session.execute(stmt)
        rows = result.scalars().all()

        return [
            BerthSegment(
                segment_id=str(row.id),
                train_number=row.train_number,
                date=row.chart_date,
                coach=row.coach,
                berth_number=row.berth_number,
                berth_type=row.berth_type,
                from_station_code=row.from_station_code,
                to_station_code=row.to_station_code,
                from_sequence=row.from_sequence,
                to_sequence=row.to_sequence,
            )
            for row in rows
        ]

    async def count_active_vacancies(
        self,
        train_number: str,
        travel_date: datetime.date,
    ) -> int:
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        stmt = (
            select(func.count(ChartVacancyORM.id))
            .where(
                ChartVacancyORM.train_number == train_number,
                ChartVacancyORM.chart_date == travel_date,
                ChartVacancyORM.status == "VACANT",
                ChartVacancyORM.expires_at > now_utc,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0

