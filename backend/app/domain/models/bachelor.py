from pydantic import BaseModel, Field, ConfigDict, field_validator, ValidationInfo
import datetime

class BerthSegment(BaseModel):
    model_config = ConfigDict(frozen=True)

    segment_id: str = Field(..., min_length=1, description="Unique identifier for segment")
    train_number: str = Field(..., min_length=1, description="Train number")
    date: datetime.date = Field(..., description="Date of journey")
    coach: str = Field(..., min_length=1, description="Coach designation e.g. B2")
    berth_number: int = Field(..., ge=1, description="Berth number (positive integer)")
    berth_type: str = Field("UB", min_length=1, description="Berth position e.g. UB, MB, LB, SL, SU")
    from_station_code: str = Field(..., min_length=1, description="Boarding station for segment")
    to_station_code: str = Field(..., min_length=1, description="Alighting station for segment")
    from_sequence: int = Field(..., ge=1, description="1-based stop sequence for boarding")
    to_sequence: int = Field(..., ge=1, description="1-based stop sequence for alighting")

    @field_validator("segment_id", "train_number", "coach", "from_station_code", "to_station_code", "berth_type")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field cannot be empty or whitespace only")
        return stripped

    @field_validator("to_sequence")
    @classmethod
    def validate_interval_order(cls, v: int, info: ValidationInfo) -> int:
        from_seq = info.data.get("from_sequence")
        if from_seq is not None and v <= from_seq:
            raise ValueError(f"to_sequence ({v}) must be greater than from_sequence ({from_seq})")
        return v

    @field_validator("to_station_code")
    @classmethod
    def validate_different_stations(cls, v: str, info: ValidationInfo) -> str:
        from_st = info.data.get("from_station_code")
        if from_st is not None and v.strip() == from_st.strip():
            raise ValueError("to_station_code cannot be identical to from_station_code")
        return v.strip()


class BachelorSpecialItinerary(BaseModel):
    model_config = ConfigDict(frozen=True)

    train_number: str = Field(..., min_length=1, description="Train number")
    train_name: str = Field(..., min_length=1, description="Train name")
    origin_code: str = Field(..., min_length=1, description="Requested origin station code")
    destination_code: str = Field(..., min_length=1, description="Requested destination station code")
    travel_date: datetime.date = Field(..., description="Date of travel")
    travel_class: str = Field(..., min_length=1, description="Travel class e.g. 3A")
    segments: list[BerthSegment] = Field(..., min_length=1, description="Ordered list of vacant berth segments")
    total_segment_count: int = Field(..., ge=1, description="Total number of berth handoffs")
    is_continuous: bool = Field(True, description="Always True for BachelorSpecialItinerary; partial coverage is not permitted")

    @field_validator("train_number", "train_name", "origin_code", "destination_code", "travel_class")
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

    @field_validator("segments")
    @classmethod
    def validate_complete_journey_segments(
        cls, v: list[BerthSegment], info: ValidationInfo
    ) -> list[BerthSegment]:
        if not v:
            raise ValueError("BachelorSpecialItinerary must contain at least one segment")

        train_num = info.data.get("train_number")
        travel_dt = info.data.get("travel_date")
        origin = info.data.get("origin_code")
        dest = info.data.get("destination_code")

        # 1. First segment starts at the requested origin
        if origin is not None and v[0].from_station_code != origin:
            raise ValueError(
                f"First segment from_station_code '{v[0].from_station_code}' must match itinerary origin_code '{origin}'"
            )

        # 2. Last segment ends at the requested destination
        if dest is not None and v[-1].to_station_code != dest:
            raise ValueError(
                f"Last segment to_station_code '{v[-1].to_station_code}' must match itinerary destination_code '{dest}'"
            )

        # 3. All segments belong to the same train and date, and have consecutive, gapless coverage
        for i, seg in enumerate(v):
            if train_num is not None and seg.train_number != train_num:
                raise ValueError(
                    f"Segment at index {i} has train_number '{seg.train_number}', "
                    f"must match itinerary train_number '{train_num}'"
                )
            if travel_dt is not None and seg.date != travel_dt:
                raise ValueError(
                    f"Segment at index {i} has date '{seg.date}', "
                    f"must match itinerary travel_date '{travel_dt}'"
                )
            if i > 0:
                prev_seg = v[i - 1]
                if prev_seg.to_station_code != seg.from_station_code:
                    raise ValueError(
                        f"Station gap detected between segment {i-1} and {i}: "
                        f"'{prev_seg.to_station_code}' != '{seg.from_station_code}'"
                    )
                if prev_seg.to_sequence != seg.from_sequence:
                    raise ValueError(
                        f"Sequence gap detected between segment {i-1} and {i}: "
                        f"{prev_seg.to_sequence} != {seg.from_sequence}"
                    )

        return v

    @field_validator("total_segment_count")
    @classmethod
    def validate_segment_count(cls, v: int, info: ValidationInfo) -> int:
        segments = info.data.get("segments")
        if segments is not None and v != len(segments):
            raise ValueError(
                f"total_segment_count ({v}) does not match the number of segments ({len(segments)})"
            )
        return v

    @field_validator("is_continuous")
    @classmethod
    def validate_is_continuous(cls, v: bool) -> bool:
        if not v:
            raise ValueError(
                "BachelorSpecialItinerary must represent a complete continuous journey; "
                "is_continuous cannot be False."
            )
        return v
