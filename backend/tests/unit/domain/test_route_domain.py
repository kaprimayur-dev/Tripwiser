import pytest
import datetime
from pydantic import ValidationError
from app.domain.models.availability import AvailabilityStatusCode, AvailabilityResult
from app.domain.models.route import JourneyLeg, CandidateRoute


@pytest.fixture
def sample_availability():
    return AvailabilityResult(
        status=AvailabilityStatusCode.AVAILABLE,
        available_count=15,
        quota="GN",
        travel_class="3A",
        fare=450.0,
        checked_at=datetime.datetime.now(),
        source="mock"
    )


def test_journey_leg_valid(sample_availability):
    now = datetime.datetime.now()
    leg = JourneyLeg(
        train_number="12616",
        train_name="GT Express",
        origin_code="GWL",
        destination_code="BPL",
        departure_time=now,
        arrival_time=now + datetime.timedelta(hours=4),
        duration_minutes=240,
        travel_class="3A",
        distance_km=390.0,
        availability=sample_availability
    )
    assert leg.train_number == "12616"
    assert leg.duration_minutes == 240


def test_journey_leg_duration_contradicts_timestamps(sample_availability):
    now = datetime.datetime.now()
    with pytest.raises(ValidationError) as exc_info:
        JourneyLeg(
            train_number="12616",
            train_name="GT Express",
            origin_code="GWL",
            destination_code="BPL",
            departure_time=now,
            arrival_time=now + datetime.timedelta(hours=2),  # 120 minutes
            duration_minutes=90,  # Contradicts timestamps (90 != 120)
            travel_class="3A",
            distance_km=390.0,
            availability=sample_availability
        )
    assert any("duration_minutes" in err["loc"] for err in exc_info.value.errors())


def test_journey_leg_arrival_before_departure(sample_availability):
    now = datetime.datetime.now()
    with pytest.raises(ValidationError) as exc_info:
        JourneyLeg(
            train_number="12616",
            train_name="GT Express",
            origin_code="GWL",
            destination_code="BPL",
            departure_time=now,
            arrival_time=now - datetime.timedelta(hours=1),  # Arrival earlier than departure
            duration_minutes=240,
            travel_class="3A",
            distance_km=390.0,
            availability=sample_availability
        )
    assert any("arrival_time" in err["loc"] for err in exc_info.value.errors())


def test_journey_leg_identical_endpoints(sample_availability):
    now = datetime.datetime.now()
    with pytest.raises(ValidationError) as exc_info:
        JourneyLeg(
            train_number="12616",
            train_name="GT Express",
            origin_code="GWL",
            destination_code="GWL",  # Same as origin
            departure_time=now,
            arrival_time=now + datetime.timedelta(hours=1),
            duration_minutes=60,
            travel_class="3A",
            distance_km=0.0,
            availability=sample_availability
        )
    assert any("destination_code" in err["loc"] for err in exc_info.value.errors())


def test_candidate_route_valid_direct(sample_availability):
    now = datetime.datetime.now()
    leg = JourneyLeg(
        train_number="12616",
        train_name="GT Express",
        origin_code="GWL",
        destination_code="BPL",
        departure_time=now,
        arrival_time=now + datetime.timedelta(hours=4),
        duration_minutes=240,
        travel_class="3A",
        distance_km=390.0,
        availability=sample_availability
    )
    route = CandidateRoute(
        route_id="route_01",
        legs=[leg],
        total_duration_minutes=240,
        total_fare=450.0,
        transfer_count=0,
        transfer_durations_minutes=[],
        is_direct=True
    )
    assert route.route_id == "route_01"
    assert route.is_direct is True
    assert route.transfer_count == 0
    assert len(route.transfer_durations_minutes) == 0


def test_candidate_route_valid_multi_leg(sample_availability):
    now = datetime.datetime.now()
    leg1 = JourneyLeg(
        train_number="12616",
        train_name="GT Express",
        origin_code="GWL",
        destination_code="JHS",
        departure_time=now,
        arrival_time=now + datetime.timedelta(hours=1),
        duration_minutes=60,
        travel_class="3A",
        distance_km=100.0,
        availability=sample_availability
    )
    leg2 = JourneyLeg(
        train_number="12002",
        train_name="Shatabdi Express",
        origin_code="JHS",
        destination_code="BPL",
        departure_time=now + datetime.timedelta(hours=2),
        arrival_time=now + datetime.timedelta(hours=5),
        duration_minutes=180,
        travel_class="3A",
        distance_km=290.0,
        availability=sample_availability
    )
    route = CandidateRoute(
        route_id="route_02",
        legs=[leg1, leg2],
        total_duration_minutes=300,
        total_fare=900.0,
        transfer_count=1,
        transfer_durations_minutes=[60],
        is_direct=False
    )
    assert route.route_id == "route_02"
    assert route.is_direct is False
    assert route.transfer_count == 1
    assert route.transfer_durations_minutes == [60]


def test_candidate_route_empty_legs():
    with pytest.raises(ValidationError) as exc_info:
        CandidateRoute(
            route_id="route_empty",
            legs=[],  # Empty legs
            total_duration_minutes=0,
            total_fare=0.0,
            transfer_count=0,
            transfer_durations_minutes=[],
            is_direct=True
        )
    assert any("legs" in err["loc"] for err in exc_info.value.errors())


def test_candidate_route_disconnected_consecutive_legs(sample_availability):
    now = datetime.datetime.now()
    leg1 = JourneyLeg(
        train_number="12616",
        train_name="GT Express",
        origin_code="GWL",
        destination_code="JHS",
        departure_time=now,
        arrival_time=now + datetime.timedelta(hours=1),
        duration_minutes=60,
        travel_class="3A",
        distance_km=100.0,
        availability=sample_availability
    )
    leg2 = JourneyLeg(
        train_number="12002",
        train_name="Shatabdi Express",
        origin_code="BHA",  # Disconnected! Expected JHS
        destination_code="BPL",
        departure_time=now + datetime.timedelta(hours=2),
        arrival_time=now + datetime.timedelta(hours=5),
        duration_minutes=180,
        travel_class="3A",
        distance_km=290.0,
        availability=sample_availability
    )

    with pytest.raises(ValidationError) as exc_info:
        CandidateRoute(
            route_id="route_disconnected",
            legs=[leg1, leg2],
            total_duration_minutes=300,
            total_fare=900.0,
            transfer_count=1,
            transfer_durations_minutes=[60],
            is_direct=False
        )
    assert any("legs" in err["loc"] for err in exc_info.value.errors())


def test_candidate_route_arrival_after_next_departure(sample_availability):
    now = datetime.datetime.now()
    leg1 = JourneyLeg(
        train_number="12616",
        train_name="GT Express",
        origin_code="GWL",
        destination_code="JHS",
        departure_time=now,
        arrival_time=now + datetime.timedelta(hours=3),  # Arrives at +3h
        duration_minutes=180,
        travel_class="3A",
        distance_km=100.0,
        availability=sample_availability
    )
    leg2 = JourneyLeg(
        train_number="12002",
        train_name="Shatabdi Express",
        origin_code="JHS",
        destination_code="BPL",
        departure_time=now + datetime.timedelta(hours=2),  # Departs earlier at +2h
        arrival_time=now + datetime.timedelta(hours=5),
        duration_minutes=180,
        travel_class="3A",
        distance_km=290.0,
        availability=sample_availability
    )

    with pytest.raises(ValidationError) as exc_info:
        CandidateRoute(
            route_id="route_invalid_timing",
            legs=[leg1, leg2],
            total_duration_minutes=300,
            total_fare=900.0,
            transfer_count=1,
            transfer_durations_minutes=[60],
            is_direct=False
        )
    assert any("legs" in err["loc"] for err in exc_info.value.errors())


def test_candidate_route_transfer_count_mismatch(sample_availability):
    now = datetime.datetime.now()
    leg1 = JourneyLeg(
        train_number="12616",
        train_name="GT Express",
        origin_code="GWL",
        destination_code="JHS",
        departure_time=now,
        arrival_time=now + datetime.timedelta(hours=1),
        duration_minutes=60,
        travel_class="3A",
        distance_km=100.0,
        availability=sample_availability
    )
    leg2 = JourneyLeg(
        train_number="12002",
        train_name="Shatabdi Express",
        origin_code="JHS",
        destination_code="BPL",
        departure_time=now + datetime.timedelta(hours=2),
        arrival_time=now + datetime.timedelta(hours=5),
        duration_minutes=180,
        travel_class="3A",
        distance_km=290.0,
        availability=sample_availability
    )

    with pytest.raises(ValidationError) as exc_info:
        CandidateRoute(
            route_id="route_02",
            legs=[leg1, leg2],
            total_duration_minutes=300,
            total_fare=900.0,
            transfer_count=2,  # Expected: len(legs) - 1 = 1
            transfer_durations_minutes=[60],
            is_direct=False
        )
    assert any("transfer_count" in err["loc"] for err in exc_info.value.errors())


def test_candidate_route_transfer_durations_length_mismatch(sample_availability):
    now = datetime.datetime.now()
    leg1 = JourneyLeg(
        train_number="12616",
        train_name="GT Express",
        origin_code="GWL",
        destination_code="JHS",
        departure_time=now,
        arrival_time=now + datetime.timedelta(hours=1),
        duration_minutes=60,
        travel_class="3A",
        distance_km=100.0,
        availability=sample_availability
    )
    leg2 = JourneyLeg(
        train_number="12002",
        train_name="Shatabdi Express",
        origin_code="JHS",
        destination_code="BPL",
        departure_time=now + datetime.timedelta(hours=2),
        arrival_time=now + datetime.timedelta(hours=5),
        duration_minutes=180,
        travel_class="3A",
        distance_km=290.0,
        availability=sample_availability
    )

    with pytest.raises(ValidationError) as exc_info:
        CandidateRoute(
            route_id="route_durations_len",
            legs=[leg1, leg2],
            total_duration_minutes=300,
            total_fare=900.0,
            transfer_count=1,
            transfer_durations_minutes=[60, 30],  # 2 entries for 1 transfer
            is_direct=False
        )
    assert any("transfer_durations_minutes" in err["loc"] for err in exc_info.value.errors())


def test_candidate_route_transfer_duration_disagrees_with_timestamps(sample_availability):
    now = datetime.datetime.now()
    leg1 = JourneyLeg(
        train_number="12616",
        train_name="GT Express",
        origin_code="GWL",
        destination_code="JHS",
        departure_time=now,
        arrival_time=now + datetime.timedelta(hours=1),  # Arrives at 10:00 (now + 1h)
        duration_minutes=60,
        travel_class="3A",
        distance_km=100.0,
        availability=sample_availability
    )
    # Next departure is at 11:30 (now + 2h30m) -> calculated transfer duration is 90 minutes
    leg2 = JourneyLeg(
        train_number="12002",
        train_name="Shatabdi Express",
        origin_code="JHS",
        destination_code="BPL",
        departure_time=now + datetime.timedelta(hours=2, minutes=30),
        arrival_time=now + datetime.timedelta(hours=5),
        duration_minutes=150,
        travel_class="3A",
        distance_km=290.0,
        availability=sample_availability
    )

    with pytest.raises(ValidationError) as exc_info:
        CandidateRoute(
            route_id="route_transfer_mismatch",
            legs=[leg1, leg2],
            total_duration_minutes=300,
            total_fare=900.0,
            transfer_count=1,
            transfer_durations_minutes=[60],  # Disagrees: calculated is 90 mins
            is_direct=False
        )
    assert any("transfer_durations_minutes" in err["loc"] for err in exc_info.value.errors())


def test_candidate_route_negative_transfer_duration(sample_availability):
    now = datetime.datetime.now()
    leg1 = JourneyLeg(
        train_number="12616",
        train_name="GT Express",
        origin_code="GWL",
        destination_code="JHS",
        departure_time=now,
        arrival_time=now + datetime.timedelta(hours=1),
        duration_minutes=60,
        travel_class="3A",
        distance_km=100.0,
        availability=sample_availability
    )
    leg2 = JourneyLeg(
        train_number="12002",
        train_name="Shatabdi Express",
        origin_code="JHS",
        destination_code="BPL",
        departure_time=now + datetime.timedelta(hours=2),
        arrival_time=now + datetime.timedelta(hours=5),
        duration_minutes=180,
        travel_class="3A",
        distance_km=290.0,
        availability=sample_availability
    )

    with pytest.raises(ValidationError) as exc_info:
        CandidateRoute(
            route_id="route_neg_duration",
            legs=[leg1, leg2],
            total_duration_minutes=300,
            total_fare=900.0,
            transfer_count=1,
            transfer_durations_minutes=[-15],  # Negative duration
            is_direct=False
        )
    assert any("transfer_durations_minutes" in err["loc"] for err in exc_info.value.errors())


def test_candidate_route_is_direct_mismatch(sample_availability):
    now = datetime.datetime.now()
    leg1 = JourneyLeg(
        train_number="12616",
        train_name="GT Express",
        origin_code="GWL",
        destination_code="JHS",
        departure_time=now,
        arrival_time=now + datetime.timedelta(hours=1),
        duration_minutes=60,
        travel_class="3A",
        distance_km=100.0,
        availability=sample_availability
    )
    leg2 = JourneyLeg(
        train_number="12002",
        train_name="Shatabdi Express",
        origin_code="JHS",
        destination_code="BPL",
        departure_time=now + datetime.timedelta(hours=2),
        arrival_time=now + datetime.timedelta(hours=5),
        duration_minutes=180,
        travel_class="3A",
        distance_km=290.0,
        availability=sample_availability
    )

    with pytest.raises(ValidationError) as exc_info:
        CandidateRoute(
            route_id="route_02",
            legs=[leg1, leg2],
            total_duration_minutes=300,
            total_fare=900.0,
            transfer_count=1,
            transfer_durations_minutes=[60],
            is_direct=True  # Inconsistent: 2 legs cannot be direct
        )
    assert any("is_direct" in err["loc"] for err in exc_info.value.errors())
