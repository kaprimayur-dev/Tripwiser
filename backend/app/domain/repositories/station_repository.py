from abc import ABC, abstractmethod
from typing import Optional
from app.domain.models.station import Station

class StationRepository(ABC):
    @abstractmethod
    async def get_by_code(self, code: str) -> Optional[Station]:
        """Retrieve a station by its station code (e.g. GWL)."""
        pass

    @abstractmethod
    async def get_by_codes(self, codes: list[str]) -> list[Station]:
        """Retrieve multiple stations by their station codes."""
        pass

    @abstractmethod
    async def search_by_name_or_code(self, query: str, limit: int = 10) -> list[Station]:
        """Search stations matching code or name for autocomplete."""
        pass

    @abstractmethod
    async def get_nearby_stations(
        self, latitude: float, longitude: float, radius_km: float
    ) -> list[tuple[Station, float]]:
        """Get stations within radius_km distance (returns list of (Station, distance_km))."""
        pass

    @abstractmethod
    async def get_nearby_stations_by_code(
        self, station_code: str, radius_km: float, limit: int = 10
    ) -> Optional[list[tuple[Station, float]]]:
        """Get stations within radius_km distance of station_code, excluding source. Returns None if station not found."""
        pass

    @abstractmethod
    async def get_station_coverage(self, station_code: str) -> dict:
        """Returns timetable coverage statistics for station_code."""
        pass

    @abstractmethod
    async def save(self, station: Station) -> Station:
        """Persist or update a station."""
        pass
