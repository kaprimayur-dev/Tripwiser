from abc import ABC, abstractmethod
from typing import Optional
from app.domain.models.train import Train

class TrainRepository(ABC):
    @abstractmethod
    async def get_by_number(self, train_number: str) -> Optional[Train]:
        """Retrieve a train by its train number (e.g. 12616)."""
        pass

    @abstractmethod
    async def find_direct_trains(self, origin_code: str, destination_code: str) -> list[Train]:
        """Find trains servicing both origin and destination in correct sequence order."""
        pass

    @abstractmethod
    async def save(self, train: Train) -> Train:
        """Persist or update a train and its schedules."""
        pass
