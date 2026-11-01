import pytest
import datetime
from pydantic import ValidationError
from app.domain.models.bachelor import BerthSegment, BachelorSpecialItinerary


@pytest.fixture
def valid_segments():
    seg1 = BerthSegment(
        segment_id="seg_01",
        train_number="12616",
        date=datetime.date(2026, 10, 15),
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
        date=datetime.date(2026, 10, 15),
        coach="B3",
        berth_number=21,
        berth_type="MB",
        from_station_code="JHS",
        to_station_code="BPL",
        from_sequence=2,
        to_sequence=3
    )
    return [seg1, seg2]


def test_bachelor_special_domain_models_valid(valid_segments):
    itinerary = BachelorSpecialItinerary(
        train_number="12616",
        train_name="Grand Trunk Express",
        origin_code="GWL",
        destination_code="BPL",
        travel_date=datetime.date(2026, 10, 15),
        travel_class="3A",
        segments=valid_segments,
        total_segment_count=2,
        is_continuous=True
    )

    assert itinerary.train_number == "12616"
    assert len(itinerary.segments) == 2
    assert itinerary.segments[0].coach == "B2"
    assert itinerary.segments[1].coach == "B3"
    assert itinerary.is_continuous is True


def test_itinerary_empty_segments_rejected():
    with pytest.raises(ValidationError) as exc_info:
        BachelorSpecialItinerary(
            train_number="12616",
            train_name="Grand Trunk Express",
            origin_code="GWL",
            destination_code="BPL",
            travel_date=datetime.date(2026, 10, 15),
            travel_class="3A",
            segments=[],  # Empty list must raise ValidationError safely, without IndexError
            total_segment_count=0,
            is_continuous=True
        )
    assert any("segments" in err["loc"] for err in exc_info.value.errors())


def test_berth_segment_invalid_berth_number_zero():
    with pytest.raises(ValidationError) as exc_info:
        BerthSegment(
            segment_id="seg_01",
            train_number="12616",
            date=datetime.date(2026, 10, 15),
            coach="B2",
            berth_number=0,  # Must be >= 1
            from_station_code="GWL",
            to_station_code="JHS",
            from_sequence=1,
            to_sequence=2
        )
    assert any("berth_number" in err["loc"] for err in exc_info.value.errors())


def test_berth_segment_invalid_berth_number_negative():
    with pytest.raises(ValidationError) as exc_info:
        BerthSegment(
            segment_id="seg_01",
            train_number="12616",
            date=datetime.date(2026, 10, 15),
            coach="B2",
            berth_number=-5,  # Must be >= 1
            from_station_code="GWL",
            to_station_code="JHS",
            from_sequence=1,
            to_sequence=2
        )
    assert any("berth_number" in err["loc"] for err in exc_info.value.errors())


def test_berth_segment_invalid_interval_order():
    with pytest.raises(ValidationError) as exc_info:
        BerthSegment(
            segment_id="seg_01",
            train_number="12616",
            date=datetime.date(2026, 10, 15),
            coach="B2",
            berth_number=10,
            from_station_code="GWL",
            to_station_code="JHS",
            from_sequence=3,
            to_sequence=2  # to_sequence <= from_sequence
        )
    assert any("to_sequence" in err["loc"] for err in exc_info.value.errors())


def test_berth_segment_invalid_equal_interval():
    with pytest.raises(ValidationError) as exc_info:
        BerthSegment(
            segment_id="seg_01",
            train_number="12616",
            date=datetime.date(2026, 10, 15),
            coach="B2",
            berth_number=10,
            from_station_code="GWL",
            to_station_code="JHS",
            from_sequence=2,
            to_sequence=2  # to_sequence == from_sequence
        )
    assert any("to_sequence" in err["loc"] for err in exc_info.value.errors())


def test_berth_segment_identical_stations():
    with pytest.raises(ValidationError) as exc_info:
        BerthSegment(
            segment_id="seg_01",
            train_number="12616",
            date=datetime.date(2026, 10, 15),
            coach="B2",
            berth_number=10,
            from_station_code="GWL",
            to_station_code="GWL",  # Identical
            from_sequence=1,
            to_sequence=2
        )
    assert any("to_station_code" in err["loc"] for err in exc_info.value.errors())


def test_itinerary_segment_count_mismatch(valid_segments):
    with pytest.raises(ValidationError) as exc_info:
        BachelorSpecialItinerary(
            train_number="12616",
            train_name="Grand Trunk Express",
            origin_code="GWL",
            destination_code="BPL",
            travel_date=datetime.date(2026, 10, 15),
            travel_class="3A",
            segments=valid_segments,
            total_segment_count=5,  # Mismatch: 5 != 2
            is_continuous=True
        )
    assert any("total_segment_count" in err["loc"] for err in exc_info.value.errors())


def test_itinerary_segment_train_mismatch():
    seg_wrong_train = BerthSegment(
        segment_id="seg_01",
        train_number="12002",  # Different train number
        date=datetime.date(2026, 10, 15),
        coach="B2",
        berth_number=43,
        from_station_code="GWL",
        to_station_code="BPL",
        from_sequence=1,
        to_sequence=2
    )

    with pytest.raises(ValidationError) as exc_info:
        BachelorSpecialItinerary(
            train_number="12616",
            train_name="Grand Trunk Express",
            origin_code="GWL",
            destination_code="BPL",
            travel_date=datetime.date(2026, 10, 15),
            travel_class="3A",
            segments=[seg_wrong_train],
            total_segment_count=1,
            is_continuous=True
        )
    assert any("segments" in err["loc"] for err in exc_info.value.errors())


def test_itinerary_segment_date_mismatch():
    seg_wrong_date = BerthSegment(
        segment_id="seg_01",
        train_number="12616",
        date=datetime.date(2026, 10, 16),  # Different date
        coach="B2",
        berth_number=43,
        from_station_code="GWL",
        to_station_code="BPL",
        from_sequence=1,
        to_sequence=2
    )

    with pytest.raises(ValidationError) as exc_info:
        BachelorSpecialItinerary(
            train_number="12616",
            train_name="Grand Trunk Express",
            origin_code="GWL",
            destination_code="BPL",
            travel_date=datetime.date(2026, 10, 15),
            travel_class="3A",
            segments=[seg_wrong_date],
            total_segment_count=1,
            is_continuous=True
        )
    assert any("segments" in err["loc"] for err in exc_info.value.errors())


def test_itinerary_first_segment_origin_mismatch():
    # Itinerary origin is GWL, but first segment starts at JHS
    seg = BerthSegment(
        segment_id="seg_01",
        train_number="12616",
        date=datetime.date(2026, 10, 15),
        coach="B2",
        berth_number=43,
        from_station_code="JHS",  # Mismatch with origin GWL
        to_station_code="BPL",
        from_sequence=2,
        to_sequence=3
    )

    with pytest.raises(ValidationError) as exc_info:
        BachelorSpecialItinerary(
            train_number="12616",
            train_name="Grand Trunk Express",
            origin_code="GWL",
            destination_code="BPL",
            travel_date=datetime.date(2026, 10, 15),
            travel_class="3A",
            segments=[seg],
            total_segment_count=1,
            is_continuous=True
        )
    assert any("segments" in err["loc"] for err in exc_info.value.errors())


def test_itinerary_last_segment_destination_mismatch():
    # Itinerary destination is BPL, but last segment ends at JHS
    seg = BerthSegment(
        segment_id="seg_01",
        train_number="12616",
        date=datetime.date(2026, 10, 15),
        coach="B2",
        berth_number=43,
        from_station_code="GWL",
        to_station_code="JHS",  # Mismatch with destination BPL
        from_sequence=1,
        to_sequence=2
    )

    with pytest.raises(ValidationError) as exc_info:
        BachelorSpecialItinerary(
            train_number="12616",
            train_name="Grand Trunk Express",
            origin_code="GWL",
            destination_code="BPL",
            travel_date=datetime.date(2026, 10, 15),
            travel_class="3A",
            segments=[seg],
            total_segment_count=1,
            is_continuous=True
        )
    assert any("segments" in err["loc"] for err in exc_info.value.errors())


def test_itinerary_station_gap_rejected():
    # Gap between JHS and BHA (segment 1 ends at JHS, segment 2 starts at BHA)
    seg1 = BerthSegment(
        segment_id="seg_01",
        train_number="12616",
        date=datetime.date(2026, 10, 15),
        coach="B2",
        berth_number=43,
        from_station_code="GWL",
        to_station_code="JHS",
        from_sequence=1,
        to_sequence=2
    )
    seg2 = BerthSegment(
        segment_id="seg_02",
        train_number="12616",
        date=datetime.date(2026, 10, 15),
        coach="B3",
        berth_number=21,
        from_station_code="BHA",  # Gap: should be JHS
        to_station_code="BPL",
        from_sequence=2,
        to_sequence=3
    )

    with pytest.raises(ValidationError) as exc_info:
        BachelorSpecialItinerary(
            train_number="12616",
            train_name="Grand Trunk Express",
            origin_code="GWL",
            destination_code="BPL",
            travel_date=datetime.date(2026, 10, 15),
            travel_class="3A",
            segments=[seg1, seg2],
            total_segment_count=2,
            is_continuous=True
        )
    assert any("segments" in err["loc"] for err in exc_info.value.errors())


def test_itinerary_sequence_gap_rejected():
    # Sequence gap: segment 1 ends at sequence 2, segment 2 starts at sequence 3
    seg1 = BerthSegment(
        segment_id="seg_01",
        train_number="12616",
        date=datetime.date(2026, 10, 15),
        coach="B2",
        berth_number=43,
        from_station_code="GWL",
        to_station_code="JHS",
        from_sequence=1,
        to_sequence=2
    )
    seg2 = BerthSegment(
        segment_id="seg_02",
        train_number="12616",
        date=datetime.date(2026, 10, 15),
        coach="B3",
        berth_number=21,
        from_station_code="JHS",
        to_station_code="BPL",
        from_sequence=3,  # Sequence gap: 3 != 2
        to_sequence=4
    )

    with pytest.raises(ValidationError) as exc_info:
        BachelorSpecialItinerary(
            train_number="12616",
            train_name="Grand Trunk Express",
            origin_code="GWL",
            destination_code="BPL",
            travel_date=datetime.date(2026, 10, 15),
            travel_class="3A",
            segments=[seg1, seg2],
            total_segment_count=2,
            is_continuous=True
        )
    assert any("segments" in err["loc"] for err in exc_info.value.errors())


def test_itinerary_cannot_masquerade_as_partial_journey(valid_segments):
    # Partial coverage cannot masquerade as valid BachelorSpecialItinerary
    with pytest.raises(ValidationError) as exc_info:
        BachelorSpecialItinerary(
            train_number="12616",
            train_name="Grand Trunk Express",
            origin_code="GWL",
            destination_code="BPL",
            travel_date=datetime.date(2026, 10, 15),
            travel_class="3A",
            segments=valid_segments,
            total_segment_count=2,
            is_continuous=False  # Cannot be False: partial coverage is not allowed
        )
    assert any("is_continuous" in err["loc"] for err in exc_info.value.errors())
