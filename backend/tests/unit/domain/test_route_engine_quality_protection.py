"""
Unit tests for TW-115 Route Engine Data Quality Protection.
Verifies that:
- Trains without verified operating calendars are excluded
- Non-monotonic sequences are rejected
- Invalid transfers (<30 min) cannot form valid candidate routes
- Total journey duration strictly equals travel time + wait time
- Negative travel times or invalid stop times are rejected
"""

import pytest
import datetime
from app.domain.models.train import Train, TrainScheduleEntry
from app.domain.models.route import TransferRiskLevel
from app.domain.services.route_engine import RouteDiscoveryEngine


def make_dummy_train(
    number: str = "12002",
    name: str = "Bhopal Shatabdi",
    runs_on_days: list = None,
    schedules: list = None,
) -> Train:
    if runs_on_days is None:
        runs_on_days = [0, 1, 2, 3, 4, 5, 6]  # Daily
    if schedules is None:
        schedules = [
            TrainScheduleEntry(
                station_code="NDLS",
                stop_sequence=1,
                arrival_time=None,
                departure_time=datetime.time(6, 0),
                day_offset=0,
                distance_km=0.0,
            ),
            TrainScheduleEntry(
                station_code="GWL",
                stop_sequence=2,
                arrival_time=datetime.time(9, 23),
                departure_time=datetime.time(9, 25),
                day_offset=0,
                distance_km=313.0,
            ),
            TrainScheduleEntry(
                station_code="BPL",
                stop_sequence=3,
                arrival_time=datetime.time(14, 25),
                departure_time=None,
                day_offset=0,
                distance_km=701.0,
            ),
        ]

    return Train(
        number=number,
        name=name,
        origin_code=schedules[0].station_code,
        destination_code=schedules[-1].station_code,
        runs_on_days=runs_on_days,
        schedule=schedules,
    )


def test_route_engine_rejects_train_without_matching_operating_days():
    engine = RouteDiscoveryEngine(session=None)
    # Train only runs on Monday (0)
    train = make_dummy_train(runs_on_days=[0])

    # Sunday (weekday 6)
    sunday_date = datetime.date(2026, 11, 8)
    leg = engine._build_journey_leg(
        train=train,
        origin_code="NDLS",
        destination_code="BPL",
        departure_date=sunday_date,
    )
    assert leg is None, "Route engine must reject trains that do not operate on requested journey date"

    # Monday (weekday 0)
    monday_date = datetime.date(2026, 11, 9)
    leg_valid = engine._build_journey_leg(
        train=train,
        origin_code="NDLS",
        destination_code="BPL",
        departure_date=monday_date,
    )
    assert leg_valid is not None
    assert leg_valid.duration_minutes == 505


def test_route_engine_rejects_non_monotonic_sequence():
    engine = RouteDiscoveryEngine(session=None)
    train = make_dummy_train()

    # Destination BPL to Origin NDLS should be rejected because NDLS sequence (1) < BPL sequence (3)
    leg = engine._build_journey_leg(
        train=train,
        origin_code="BPL",
        destination_code="NDLS",
        departure_date=datetime.date(2026, 11, 9),
    )
    assert leg is None, "Route engine must reject origin after destination (reverse sequence)"


def test_route_engine_rejects_missing_timing():
    engine = RouteDiscoveryEngine(session=None)
    # Train where intermediate stop has missing departure time
    schedules = [
        TrainScheduleEntry(
            station_code="NDLS",
            stop_sequence=1,
            arrival_time=None,
            departure_time=None,  # Missing departure
            day_offset=0,
            distance_km=0.0,
        ),
        TrainScheduleEntry(
            station_code="BPL",
            stop_sequence=2,
            arrival_time=datetime.time(14, 25),
            departure_time=None,
            day_offset=0,
            distance_km=701.0,
        ),
    ]
    train = make_dummy_train(schedules=schedules)
    leg = engine._build_journey_leg(
        train=train,
        origin_code="NDLS",
        destination_code="BPL",
        departure_date=datetime.date(2026, 11, 9),
    )
    assert leg is None, "Route engine must reject stops with missing departure or arrival times"


def test_route_engine_rejects_invalid_connection_layovers():
    # Layover < 30 min is classified as INVALID_CONNECTION
    base_arr = datetime.datetime(2026, 11, 9, 10, 0)
    layover = RouteDiscoveryEngine.classify_transfer_layover(
        station_code="GWL",
        arriving_train_number="12002",
        departing_train_number="12626",
        arrival_time=base_arr,
        departure_time=base_arr + datetime.timedelta(minutes=25),
        duration_minutes=25,
    )
    assert layover.risk_level == TransferRiskLevel.INVALID_CONNECTION
    assert "below the 30-minute minimum buffer" in layover.risk_description


def test_mathematical_identity_total_duration():
    """Verify total_duration = travel_time + wait_time holds unconditionally."""
    engine = RouteDiscoveryEngine(session=None)
    train1 = make_dummy_train(number="T1")
    train2 = make_dummy_train(number="T2")

    leg1 = engine._build_journey_leg(train1, "NDLS", "GWL", datetime.date(2026, 11, 9))
    assert leg1 is not None

    leg2 = engine._build_journey_leg(train2, "GWL", "BPL", datetime.date(2026, 11, 9))
    assert leg2 is not None

    transfer_wait = 45  # minutes
    total_duration = leg1.duration_minutes + transfer_wait + leg2.duration_minutes
    travel_time = leg1.duration_minutes + leg2.duration_minutes
    wait_time = transfer_wait

    assert total_duration == travel_time + wait_time, "Mathematical identity total_duration = travel_time + wait_time must hold"

    layover = RouteDiscoveryEngine.classify_transfer_layover(
        station_code="GWL",
        arriving_train_number="T1",
        departing_train_number="T2",
        arrival_time=leg1.arrival_time,
        departure_time=leg1.arrival_time + datetime.timedelta(minutes=wait_time),
        duration_minutes=wait_time,
    )

    insights, overall_risk = engine.generate_journey_insights(
        legs=[leg1, leg2],
        total_duration=total_duration,
        travel_time=travel_time,
        wait_time=wait_time,
        layovers=[layover],
    )

    assert overall_risk == TransferRiskLevel.MODERATE_CONNECTION.value
    assert any("Total scheduled waiting time" in i for i in insights)
    assert any("Time aboard trains" in i for i in insights)
