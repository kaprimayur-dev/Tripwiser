from pydantic import BaseModel, Field, ConfigDict
import datetime

class BerthSegment(BaseModel):
    model_config = ConfigDict(frozen=True)

    segment_id: str = Field(..., description="Unique identifier for segment")
    train_number: str = Field(..., description="Train number")
    date: datetime.date = Field(..., description="Date of journey")
    coach: str = Field(..., description="Coach designation e.g. B2")
    berth_number: int = Field(..., ge=1, description="Berth number")
    berth_type: str = Field("UB", description="Berth position e.g. UB, MB, LB, SL, SU")
    from_station_code: str = Field(..., description="Boarding station for segment")
    to_station_code: str = Field(..., description="Alighting station for segment")
    from_sequence: int = Field(..., ge=1, description="1-based stop sequence for boarding")
    to_sequence: int = Field(..., ge=1, description="1-based stop sequence for alighting")

class BachelorSpecialItinerary(BaseModel):
    model_config = ConfigDict(frozen=True)

    train_number: str = Field(..., description="Train number")
    train_name: str = Field(..., description="Train name")
    origin_code: str = Field(..., description="Requested origin station code")
    destination_code: str = Field(..., description="Requested destination station code")
    travel_date: datetime.date = Field(..., description="Date of travel")
    travel_class: str = Field(..., description="Travel class e.g. 3A")
    segments: list[BerthSegment] = Field(default_factory=list, description="Ordered list of vacant berth segments")
    total_segment_count: int = Field(0, ge=0, description="Total number of berth handoffs")
    is_continuous: bool = Field(True, description="True if segments provide gapless origin-to-destination coverage")
