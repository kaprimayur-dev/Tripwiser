from pydantic import BaseModel, Field, ConfigDict, field_validator, ValidationInfo
from typing import Optional
import datetime

class TrainScheduleEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    station_code: str = Field(..., min_length=1, description="Station code")
    arrival_time: Optional[datetime.time] = Field(None, description="Arrival time at station")
    departure_time: Optional[datetime.time] = Field(None, description="Departure time from station")
    day_offset: int = Field(0, ge=0, description="Day offset (0 for origin day, 1 for next day)")
    distance_km: float = Field(0.0, ge=0.0, description="Cumulative distance in KM")
    stop_sequence: int = Field(..., ge=1, description="1-based stop sequence")

    @field_validator("station_code")
    @classmethod
    def validate_station_code(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Station code cannot be empty or whitespace only")
        return stripped


class Train(BaseModel):
    model_config = ConfigDict(frozen=True)

    number: str = Field(..., min_length=1, description="Train number e.g. 12616")
    name: str = Field(..., min_length=1, description="Train name e.g. Grand Trunk Express")
    origin_code: str = Field(..., min_length=1, description="Origin station code")
    destination_code: str = Field(..., min_length=1, description="Destination station code")
    runs_on_days: list[int] = Field(..., description="List of days of week train runs (0=Mon, 6=Sun)")
    schedule: list[TrainScheduleEntry] = Field(..., min_length=1, description="Ordered schedule stops")

    @field_validator("number", "name", "origin_code", "destination_code")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field cannot be empty or whitespace only")
        return stripped

    @field_validator("destination_code")
    @classmethod
    def validate_distinct_endpoints(cls, v: str, info: ValidationInfo) -> str:
        orig = info.data.get("origin_code")
        if orig is not None and v.strip() == orig.strip():
            raise ValueError("destination_code cannot be identical to origin_code")
        return v.strip()

    @field_validator("runs_on_days")
    @classmethod
    def validate_runs_on_days(cls, v: list[int]) -> list[int]:
        if not v:
            raise ValueError("runs_on_days cannot be empty")
        for day in v:
            if not (0 <= day <= 6):
                raise ValueError(f"Running day {day} must be between 0 (Monday) and 6 (Sunday)")
        if len(v) != len(set(v)):
            raise ValueError("runs_on_days must not contain duplicates")
        return v

    @field_validator("schedule")
    @classmethod
    def validate_schedule_integrity(
        cls, schedule: list[TrainScheduleEntry], info: ValidationInfo
    ) -> list[TrainScheduleEntry]:
        if not schedule:
            raise ValueError("Train schedule must not be empty")

        origin = info.data.get("origin_code")
        destination = info.data.get("destination_code")

        if origin is not None and schedule[0].station_code != origin:
            raise ValueError(
                f"First schedule station '{schedule[0].station_code}' must match train origin_code '{origin}'"
            )

        if destination is not None and schedule[-1].station_code != destination:
            raise ValueError(
                f"Last schedule station '{schedule[-1].station_code}' must match train destination_code '{destination}'"
            )

        prev_seq = None
        for entry in schedule:
            if prev_seq is not None and entry.stop_sequence <= prev_seq:
                raise ValueError(
                    f"Schedule stop sequences must be strictly increasing. "
                    f"Found stop_sequence {entry.stop_sequence} following {prev_seq}."
                )
            prev_seq = entry.stop_sequence

        return schedule
