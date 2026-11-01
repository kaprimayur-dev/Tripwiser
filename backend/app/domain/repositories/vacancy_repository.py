from abc import ABC, abstractmethod
from typing import Optional
import datetime
from app.domain.models.bachelor import BerthSegment

class VacancyRepository(ABC):
    @abstractmethod
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
        pass

    @abstractmethod
    async def count_active_vacancies(
        self,
        train_number: str,
        travel_date: datetime.date,
    ) -> int:
        """Count active, unexpired vacant berth segments for a given train and date."""
        pass

