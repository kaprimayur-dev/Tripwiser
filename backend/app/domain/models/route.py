from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator, ValidationInfo
import datetime
from app.domain.models.availability import AvailabilityResult

class JourneyLeg(BaseModel):
    model_config = ConfigDict(frozen=True)

    train_number: str = Field(..., min_length=1)
    train_name: str = Field(..., min_length=1)
    origin_code: str = Field(..., min_length=1)
    destination_code: str = Field(..., min_length=1)
    departure_time: datetime.datetime
    arrival_time: datetime.datetime
    duration_minutes: int = Field(..., ge=0)
    travel_class: Optional[str] = Field(None)
    distance_km: float = Field(..., ge=0.0)
    availability: Optional[AvailabilityResult] = None

    @field_validator("train_number", "train_name", "origin_code", "destination_code")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field cannot be empty or whitespace only")
        return stripped

    @field_validator("travel_class")
    @classmethod
    def validate_travel_class(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field cannot be empty or whitespace only")
        return stripped

    @field_validator("destination_code")
    @classmethod
    def validate_different_stations(cls, v: str, info: ValidationInfo) -> str:
        orig = info.data.get("origin_code")
        if orig is not None and v.strip() == orig.strip():
            raise ValueError("destination_code cannot be identical to origin_code")
        return v.strip()

    @field_validator("arrival_time")
    @classmethod
    def validate_arrival_time(cls, v: datetime.datetime, info: ValidationInfo) -> datetime.datetime:
        dep = info.data.get("departure_time")
        if dep is not None and v < dep:
            raise ValueError("arrival_time cannot be earlier than departure_time")
        return v

    @field_validator("duration_minutes")
    @classmethod
    def validate_duration_minutes(cls, v: int, info: ValidationInfo) -> int:
        dep = info.data.get("departure_time")
        arr = info.data.get("arrival_time")
        if dep is not None and arr is not None and arr >= dep:
            expected_mins = int((arr - dep).total_seconds() // 60)
            if v != expected_mins:
                raise ValueError(
                    f"duration_minutes ({v}) must agree with arrival_time - departure_time ({expected_mins} minutes)"
                )
        return v


class CandidateRoute(BaseModel):
    model_config = ConfigDict(frozen=True)

    route_id: str = Field(..., min_length=1)
    legs: list[JourneyLeg] = Field(..., min_length=1)
    total_duration_minutes: int = Field(..., ge=0)
    total_fare: Optional[float] = Field(None, ge=0.0)
    transfer_count: int = Field(..., ge=0)
    transfer_durations_minutes: list[int] = Field(default_factory=list)
    is_direct: bool
    score: float = 0.0

    @field_validator("route_id")
    @classmethod
    def validate_route_id(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("route_id cannot be empty or whitespace only")
        return stripped

    @field_validator("legs")
    @classmethod
    def validate_legs_connectivity(cls, legs: list[JourneyLeg]) -> list[JourneyLeg]:
        if not legs:
            raise ValueError("CandidateRoute must contain at least one JourneyLeg")

        for i in range(len(legs) - 1):
            if legs[i].destination_code != legs[i + 1].origin_code:
                raise ValueError(
                    f"Consecutive legs must connect at the same station. "
                    f"Leg {i} destination is '{legs[i].destination_code}', but Leg {i+1} origin is '{legs[i+1].origin_code}'"
                )
            if legs[i].arrival_time > legs[i + 1].departure_time:
                raise ValueError(
                    f"Previous leg arrival time ({legs[i].arrival_time}) cannot be later than "
                    f"next leg departure time ({legs[i+1].departure_time})"
                )

        return legs

    @field_validator("transfer_count")
    @classmethod
    def validate_transfers(cls, v: int, info: ValidationInfo) -> int:
        legs = info.data.get("legs")
        if legs is not None:
            expected_transfers = len(legs) - 1
            if v != expected_transfers:
                raise ValueError(
                    f"transfer_count ({v}) must equal len(legs) - 1 ({expected_transfers})"
                )
        return v

    @field_validator("transfer_durations_minutes")
    @classmethod
    def validate_transfer_durations(cls, v: list[int], info: ValidationInfo) -> list[int]:
        legs: list[JourneyLeg] = info.data.get("legs")
        expected_transfers = len(legs) - 1 if legs is not None else info.data.get("transfer_count")

        if expected_transfers is not None and len(v) != expected_transfers:
            raise ValueError(
                f"transfer_durations_minutes must contain exactly one value per transfer "
                f"(expected {expected_transfers}, got {len(v)})"
            )

        for d in v:
            if d < 0:
                raise ValueError(f"Transfer duration must be non-negative: {d}")

        if legs is not None and len(legs) > 1:
            for i in range(len(legs) - 1):
                prev_arr = legs[i].arrival_time
                next_dep = legs[i + 1].departure_time
                expected_mins = int((next_dep - prev_arr).total_seconds() // 60)
                if i < len(v) and v[i] != expected_mins:
                    raise ValueError(
                        f"Transfer duration at index {i} ({v[i]} minutes) does not agree with "
                        f"calculated duration ({expected_mins} minutes) between Leg {i} arrival "
                        f"({prev_arr}) and Leg {i+1} departure ({next_dep})"
                    )

        return v

    @field_validator("is_direct")
    @classmethod
    def validate_is_direct(cls, v: bool, info: ValidationInfo) -> bool:
        legs = info.data.get("legs")
        if legs is not None:
            expected_direct = (len(legs) == 1)
            if v != expected_direct:
                raise ValueError(
                    f"is_direct ({v}) is inconsistent with leg count ({len(legs)})"
                )
        return v
