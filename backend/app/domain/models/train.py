from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
import datetime

class TrainScheduleEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    station_code: str = Field(..., description="Station code")
    arrival_time: Optional[datetime.time] = Field(None, description="Arrival time at station")
    departure_time: Optional[datetime.time] = Field(None, description="Departure time from station")
    day_offset: int = Field(0, ge=0, description="Day offset (0 for origin day, 1 for next day)")
    distance_km: float = Field(0.0, ge=0.0, description="Cumulative distance in KM")
    stop_sequence: int = Field(..., ge=1, description="1-based stop sequence")

class Train(BaseModel):
    model_config = ConfigDict(frozen=True)

    number: str = Field(..., description="Train number e.g. 12616")
    name: str = Field(..., description="Train name e.g. Grand Trunk Express")
    origin_code: str = Field(..., description="Origin station code")
    destination_code: str = Field(..., description="Destination station code")
    runs_on_days: list[int] = Field(..., description="List of days of week train runs (0=Mon, 6=Sun)")
    schedule: list[TrainScheduleEntry] = Field(default_factory=list, description="Ordered schedule stops")
