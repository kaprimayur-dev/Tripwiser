from enum import Enum
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional
import datetime

class AvailabilityStatusCode(str, Enum):
    AVAILABLE = "AVAILABLE"
    RAC = "RAC"
    WAITLIST = "WAITLIST"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    CHARTING_PENDING = "CHARTING_PENDING"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    STALE = "STALE"

class AvailabilityResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: AvailabilityStatusCode
    available_count: Optional[int] = Field(None, ge=0, description="Number of available seats/berths")
    waitlist_count: Optional[int] = Field(None, ge=0, description="Waitlist number if applicable")
    quota: Optional[str] = Field(None, description="Quota code e.g. GN, TQ")
    travel_class: Optional[str] = Field(None, description="Travel class e.g. SL, 3A, 2A, 1A")
    fare: Optional[float] = Field(None, ge=0.0, description="Total fare for leg")
    checked_at: datetime.datetime = Field(..., description="Timestamp when availability was fetched")
    source: str = Field("mock", min_length=1, description="Provider identifier")

    @field_validator("quota", "travel_class", "source")
    @classmethod
    def validate_non_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field cannot be empty or whitespace only")
        return stripped
