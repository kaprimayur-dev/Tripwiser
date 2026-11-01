import pytest
import datetime
from app.domain.models.bachelor import BerthSegment
from app.domain.services.bachelor_engine import BachelorEngine


@pytest.fixture
def sample_vacancies():
    d = datetime.date(2026, 11, 4)
    return [
        # Segment 1: GWL -> JHS (seq 42 -> 52) Coach B2, Berth 43
        BerthSegment(
            segment_id="v1",
            train_number="12002",
            date=d,
            coach="B2",
            berth_number=43,
            berth_type="UB",
            from_station_code="GWL",
            to_station_code="JHS",
            from_sequence=42,
            to_sequence=52,
        ),
        # Segment 2: JHS -> BHS (seq 52 -> 81) Coach B3, Berth 21
        BerthSegment(
            segment_id="v2",
            train_number="12002",
            date=d,
            coach="B3",
            berth_number=21,
            berth_type="MB",
            from_station_code="JHS",
            to_station_code="BHS",
            from_sequence=52,
            to_sequence=81,
        ),
        # Segment 3: BHS -> BPL (seq 81 -> 87) Coach B1, Berth 18
        BerthSegment(
            segment_id="v3",
            train_number="12002",
            date=d,
            coach="B1",
            berth_number=18,
            berth_type="LB",
            from_station_code="BHS",
            to_station_code="BPL",
            from_sequence=81,
            to_sequence=87,
        ),
        # Alternative direct segment: JHS -> BPL (seq 52 -> 87) Coach B2, Berth 44
        BerthSegment(
            segment_id="v4",
            train_number="12002",
            date=d,
            coach="B2",
            berth_number=44,
            berth_type="UB",
            from_station_code="JHS",
            to_station_code="BPL",
            from_sequence=52,
            to_sequence=87,
        ),
    ]


def test_bachelor_engine_discovers_continuous_paths(sample_vacancies):
    engine = BachelorEngine(max_segments=4)
    d = datetime.date(2026, 11, 4)

    itineraries = engine.discover_itineraries(
        train_number="12002",
        train_name="New Delhi-Bhopal Shatabdi Express",
        origin_code="GWL",
        destination_code="BPL",
        origin_sequence=42,
        destination_sequence=87,
        travel_date=d,
        travel_class="3A",
        candidate_vacancies=sample_vacancies,
    )

    # Should discover 2 valid paths:
    # Option A: 2 segments (GWL->JHS via v1, JHS->BPL via v4) -> 1 berth change
    # Option B: 3 segments (GWL->JHS via v1, JHS->BHS via v2, BHS->BPL via v3) -> 2 berth changes
    assert len(itineraries) == 2

    # Verification of ranking: Option A (1 change) must be first!
    first = itineraries[0]
    assert first.total_segment_count == 2
    assert first.segments[0].segment_id == "v1"
    assert first.segments[1].segment_id == "v4"
    assert first.is_continuous is True

    # Option B (2 changes) ranked second
    second = itineraries[1]
    assert second.total_segment_count == 3
    assert second.segments[0].segment_id == "v1"
    assert second.segments[1].segment_id == "v2"
    assert second.segments[2].segment_id == "v3"
    assert second.is_continuous is True


def test_bachelor_engine_rejects_gaps():
    engine = BachelorEngine()
    d = datetime.date(2026, 11, 4)

    # Missing JHS -> BHS link
    gapped_vacancies = [
        BerthSegment(
            segment_id="v1",
            train_number="12002",
            date=d,
            coach="B2",
            berth_number=43,
            from_station_code="GWL",
            to_station_code="JHS",
            from_sequence=42,
            to_sequence=52,
        ),
        BerthSegment(
            segment_id="v3",
            train_number="12002",
            date=d,
            coach="B1",
            berth_number=18,
            from_station_code="BHS",
            to_station_code="BPL",
            from_sequence=81,
            to_sequence=87,
        ),
    ]

    itineraries = engine.discover_itineraries(
        train_number="12002",
        train_name="Shatabdi Express",
        origin_code="GWL",
        destination_code="BPL",
        origin_sequence=42,
        destination_sequence=87,
        travel_date=d,
        travel_class="3A",
        candidate_vacancies=gapped_vacancies,
    )

    assert itineraries == []


def test_bachelor_engine_rejects_overlaps():
    engine = BachelorEngine()
    d = datetime.date(2026, 11, 4)

    # Overlapping sequences: 42->60 and 52->87
    overlapping_vacancies = [
        BerthSegment(
            segment_id="v1",
            train_number="12002",
            date=d,
            coach="B2",
            berth_number=43,
            from_station_code="GWL",
            to_station_code="BJA",
            from_sequence=42,
            to_sequence=60,
        ),
        BerthSegment(
            segment_id="v2",
            train_number="12002",
            date=d,
            coach="B3",
            berth_number=21,
            from_station_code="JHS",
            to_station_code="BPL",
            from_sequence=52,
            to_sequence=87,
        ),
    ]

    itineraries = engine.discover_itineraries(
        train_number="12002",
        train_name="Shatabdi Express",
        origin_code="GWL",
        destination_code="BPL",
        origin_sequence=42,
        destination_sequence=87,
        travel_date=d,
        travel_class="3A",
        candidate_vacancies=overlapping_vacancies,
    )

    assert itineraries == []


def test_bachelor_engine_rejects_wrong_train_and_date():
    engine = BachelorEngine()
    d = datetime.date(2026, 11, 4)

    vacancies = [
        # Wrong train
        BerthSegment(
            segment_id="v1",
            train_number="12951",
            date=d,
            coach="B2",
            berth_number=43,
            from_station_code="GWL",
            to_station_code="JHS",
            from_sequence=42,
            to_sequence=52,
        ),
        # Wrong date
        BerthSegment(
            segment_id="v2",
            train_number="12002",
            date=datetime.date(2026, 11, 5),
            coach="B2",
            berth_number=44,
            from_station_code="JHS",
            to_station_code="BPL",
            from_sequence=52,
            to_sequence=87,
        ),
    ]

    itineraries = engine.discover_itineraries(
        train_number="12002",
        train_name="Shatabdi Express",
        origin_code="GWL",
        destination_code="BPL",
        origin_sequence=42,
        destination_sequence=87,
        travel_date=d,
        travel_class="3A",
        candidate_vacancies=vacancies,
    )

    assert itineraries == []


def test_bachelor_engine_empty_vacancies():
    engine = BachelorEngine()
    d = datetime.date(2026, 11, 4)

    itineraries = engine.discover_itineraries(
        train_number="12002",
        train_name="Shatabdi Express",
        origin_code="GWL",
        destination_code="BPL",
        origin_sequence=42,
        destination_sequence=87,
        travel_date=d,
        travel_class="3A",
        candidate_vacancies=[],
    )

    assert itineraries == []

