from pydantic import BaseModel, Field, ConfigDict
import datetime
from app.domain.models.availability import AvailabilityResult

class JourneyLeg(BaseModel):
    model_config = ConfigDict(frozen=True)

    train_number: str
    train_name: str
    origin_code: str
    destination_code: str
    departure_time: datetime.datetime
    arrival_time: datetime.datetime
    duration_minutes: int = Field(..., ge=0)
    travel_class: str
    distance_km: float = Field(..., ge=0.0)
    availability: AvailabilityResult

class CandidateRoute(BaseModel):
    model_config = ConfigDict(frozen=True)

    route_id: str
    legs: list[JourneyLeg]
    total_duration_minutes: int = Field(..., ge=0)
    total_fare: float = Field(..., ge=0.0)
    transfer_count: int = Field(..., ge=0)
    transfer_durations_minutes: list[int] = Field(default_factory=list)
    is_direct: bool
    score: float = 0.0
