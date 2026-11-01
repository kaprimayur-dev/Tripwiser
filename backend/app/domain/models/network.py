"""
Domain models for railway network intelligence, station-to-station connectivity,
and interchange junction discovery.
"""

from typing import List, Optional
from dataclasses import dataclass, field
import datetime


@dataclass(frozen=True)
class TrainConnectivity:
    train_number: str
    train_name: str
    origin_code: str
    destination_code: str
    departure_time: datetime.time
    arrival_time: datetime.time
    day_difference: int
    duration_minutes: int
    distance_km: float
    runs_on_days: List[int]
    intermediate_stop_count: int
    origin_stop_sequence: int
    destination_stop_sequence: int


@dataclass
class StationConnectivityResult:
    origin_code: str
    destination_code: str
    trains: List[TrainConnectivity] = field(default_factory=list)
    total_trains_count: int = 0
    fastest_duration_minutes: Optional[int] = None
    average_duration_minutes: Optional[int] = None


@dataclass(frozen=True)
class InterchangeStation:
    station_code: str
    station_name: str
    city: Optional[str]
    state: Optional[str]
    zone: Optional[str]
    latitude: float
    longitude: float
    inbound_trains_count: int
    outbound_trains_count: int
    connection_score: int
    sample_inbound_trains: List[str] = field(default_factory=list)
    sample_outbound_trains: List[str] = field(default_factory=list)
