import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.bachelor import BachelorSpecialItinerary, BachelorSpecialSearchResult
from app.domain.repositories.train_repository import TrainRepository
from app.domain.repositories.vacancy_repository import VacancyRepository
from app.domain.services.bachelor_engine import BachelorEngine
from app.infrastructure.database.repositories.train_repository import SQLAlchemyTrainRepository
from app.infrastructure.database.repositories.vacancy_repository import PostgresVacancyRepository


class BachelorSpecialService:
    def __init__(
        self,
        session: AsyncSession,
        train_repo: Optional[TrainRepository] = None,
        vacancy_repo: Optional[VacancyRepository] = None,
        engine: Optional[BachelorEngine] = None,
    ):
        self.session = session
        self.train_repo = train_repo or SQLAlchemyTrainRepository(session)
        self.vacancy_repo = vacancy_repo or PostgresVacancyRepository(session)
        self.engine = engine or BachelorEngine()

    async def search_bachelor_special(
        self,
        origin_code: str,
        destination_code: str,
        travel_date: datetime.date,
        travel_class: Optional[str] = None,
    ) -> BachelorSpecialSearchResult:
        orig_clean = origin_code.strip().upper()
        dest_clean = destination_code.strip().upper()
        class_clean = travel_class.strip().upper() if travel_class else None

        # 1. Find direct trains connecting origin and destination
        direct_trains = await self.train_repo.find_direct_trains(orig_clean, dest_clean)
        if not direct_trains:
            return BachelorSpecialSearchResult(
                origin_code=orig_clean,
                destination_code=dest_clean,
                travel_date=travel_date,
                travel_class=class_clean,
                total_itineraries=0,
                itineraries=[],
                status="NO_DIRECT_TRAINS",
            )

        # 2. Filter trains operating on travel_date
        operating_trains = []
        for train in direct_trains:
            # Find origin and destination schedule entries
            orig_stop = next((s for s in train.schedule if s.station_code == orig_clean), None)
            dest_stop = next((s for s in train.schedule if s.station_code == dest_clean), None)
            if not orig_stop or not dest_stop or orig_stop.stop_sequence >= dest_stop.stop_sequence:
                continue

            # Check operating day with day offset
            train_start_date = travel_date - datetime.timedelta(days=orig_stop.day_offset)
            if train_start_date.weekday() not in train.runs_on_days:
                continue

            operating_trains.append((train, orig_stop, dest_stop))

        if not operating_trains:
            return BachelorSpecialSearchResult(
                origin_code=orig_clean,
                destination_code=dest_clean,
                travel_date=travel_date,
                travel_class=class_clean,
                total_itineraries=0,
                itineraries=[],
                status="NO_DIRECT_TRAINS",
            )

        # 3. For each operating train, query vacancies and run BachelorEngine
        all_itineraries: list[BachelorSpecialItinerary] = []
        default_class = class_clean or "3A"

        for train, orig_stop, dest_stop in operating_trains:
            vacancies = await self.vacancy_repo.get_vacancies_for_train(
                train_number=train.number,
                travel_date=travel_date,
                min_seq=orig_stop.stop_sequence,
                max_seq=dest_stop.stop_sequence,
                travel_class=class_clean,
            )

            if not vacancies:
                continue

            discovered = self.engine.discover_itineraries(
                train_number=train.number,
                train_name=train.name,
                origin_code=orig_clean,
                destination_code=dest_clean,
                origin_sequence=orig_stop.stop_sequence,
                destination_sequence=dest_stop.stop_sequence,
                travel_date=travel_date,
                travel_class=default_class,
                candidate_vacancies=vacancies,
            )
            all_itineraries.extend(discovered)

        # Rank combined results across trains
        ranked_all = self.engine._rank_itineraries(all_itineraries)

        status = "SUCCESS" if ranked_all else "NO_CHART_VACANCIES"

        return BachelorSpecialSearchResult(
            origin_code=orig_clean,
            destination_code=dest_clean,
            travel_date=travel_date,
            travel_class=class_clean,
            total_itineraries=len(ranked_all),
            itineraries=ranked_all,
            status=status,
        )

