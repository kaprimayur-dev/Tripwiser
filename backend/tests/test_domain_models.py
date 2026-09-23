import pytest
from datetime import time, date, datetime
from pydantic import ValidationError

from app.domain.models.station import Station
from app.domain.models.train import Train, TrainScheduleEntry
from app.domain.models.availability import AvailabilityStatusCode, AvailabilityResult
from app.domain.models.route import JourneyLeg, CandidateRoute
from app.domain.models.bachelor import BerthSegment, BachelorSpecialItinerary


def test_station_domain_model_valid():
    station = Station(
        code="GWL",
        name="Gwalior Junction",
        latitude=26.2183,
        longitude=78.1828,
        city="Gwalior",
        state="Madhya Pradesh",
        zone="NCR"
    )
    assert station.code == "GWL"
    assert station.name == "Gwalior Junction"
    assert station.latitude == 26.2183
    assert station.longitude == 78.1828


def test_station_domain_model_invalid_coordinates():
    with pytest.raises(ValidationError):
        Station(
            code="GWL",
            name="Gwalior Junction",
            latitude=105.0,  # Invalid latitude (>90)
            longitude=78.1828
        )


def test_train_and_schedule_domain_models():
    entry1 = TrainScheduleEntry(
        station_code="GWL",
        departure_time=time(6, 15),
        day_offset=0,
        distance_km=0.0,
        stop_sequence=1
    )
    entry2 = TrainScheduleEntry(
        station_code="BPL",
        arrival_time=time(10, 45),
        day_offset=0,
        distance_km=390.0,
        stop_sequence=2
    )
    train = Train(
        number="12616",
        name="Grand Trunk Express",
        origin_code="GWL",
        destination_code="BPL",
        runs_on_days=[0, 1, 2, 3, 4, 5, 6],
        schedule=[entry1, entry2]
    )

    assert train.number == "12616"
    assert len(train.schedule) == 2
    assert train.schedule[0].station_code == "GWL"
    assert train.schedule[1].distance_km == 390.0


def test_availability_status_enum_all_states():
    approved_states = [
        "AVAILABLE",
        "RAC",
        "WAITLIST",
        "NOT_AVAILABLE",
        "CHARTING_PENDING",
        "PROVIDER_ERROR",
        "STALE",
    ]
    for state_str in approved_states:
        enum_val = AvailabilityStatusCode(state_str)
        assert enum_val.value == state_str

    assert len(AvailabilityStatusCode) == 7


def test_availability_result_valid():
    res = AvailabilityResult(
        status=AvailabilityStatusCode.AVAILABLE,
        available_count=24,
        quota="GN",
        travel_class="3A",
        fare=750.0,
        checked_at=datetime.now(),
        source="mock"
    )
    assert res.status == AvailabilityStatusCode.AVAILABLE
    assert res.available_count == 24
    assert res.fare == 750.0


def test_bachelor_special_domain_models():
    seg1 = BerthSegment(
        segment_id="seg_01",
        train_number="12616",
        date=date(2026, 10, 15),
        coach="B2",
        berth_number=43,
        berth_type="UB",
        from_station_code="GWL",
        to_station_code="JHS",
        from_sequence=1,
        to_sequence=2
    )
    seg2 = BerthSegment(
        segment_id="seg_02",
        train_number="12616",
        date=date(2026, 10, 15),
        coach="B3",
        berth_number=21,
        berth_type="MB",
        from_station_code="JHS",
        to_station_code="BPL",
        from_sequence=2,
        to_sequence=3
    )

    itinerary = BachelorSpecialItinerary(
        train_number="12616",
        train_name="Grand Trunk Express",
        origin_code="GWL",
        destination_code="BPL",
        travel_date=date(2026, 10, 15),
        travel_class="3A",
        segments=[seg1, seg2],
        total_segment_count=2,
        is_continuous=True
    )

    assert itinerary.train_number == "12616"
    assert len(itinerary.segments) == 2
    assert itinerary.segments[0].coach == "B2"
    assert itinerary.segments[1].coach == "B3"
    assert itinerary.is_continuous is True
