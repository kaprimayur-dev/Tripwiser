import pytest
import datetime
from pydantic import ValidationError
from app.domain.models.train import Train, TrainScheduleEntry


@pytest.fixture
def valid_schedule():
    entry1 = TrainScheduleEntry(
        station_code="GWL",
        departure_time=datetime.time(6, 15),
        day_offset=0,
        distance_km=0.0,
        stop_sequence=1
    )
    entry2 = TrainScheduleEntry(
        station_code="BPL",
        arrival_time=datetime.time(10, 45),
        day_offset=0,
        distance_km=390.0,
        stop_sequence=2
    )
    return [entry1, entry2]


def test_train_and_schedule_domain_models_valid(valid_schedule):
    train = Train(
        number="12616",
        name="Grand Trunk Express",
        origin_code="GWL",
        destination_code="BPL",
        runs_on_days=[0, 1, 2, 3, 4, 5, 6],
        schedule=valid_schedule
    )

    assert train.number == "12616"
    assert len(train.schedule) == 2
    assert train.schedule[0].station_code == "GWL"
    assert train.schedule[1].distance_km == 390.0


def test_train_schedule_entry_invalid_sequence_zero():
    with pytest.raises(ValidationError) as exc_info:
        TrainScheduleEntry(
            station_code="GWL",
            stop_sequence=0  # Must be >= 1
        )
    assert any("stop_sequence" in err["loc"] for err in exc_info.value.errors())


def test_train_schedule_entry_invalid_sequence_negative():
    with pytest.raises(ValidationError) as exc_info:
        TrainScheduleEntry(
            station_code="GWL",
            stop_sequence=-2  # Must be >= 1
        )
    assert any("stop_sequence" in err["loc"] for err in exc_info.value.errors())


def test_train_schedule_entry_invalid_distance():
    with pytest.raises(ValidationError) as exc_info:
        TrainScheduleEntry(
            station_code="GWL",
            stop_sequence=1,
            distance_km=-10.5  # Must be >= 0.0
        )
    assert any("distance_km" in err["loc"] for err in exc_info.value.errors())


def test_train_schedule_entry_invalid_day_offset():
    with pytest.raises(ValidationError) as exc_info:
        TrainScheduleEntry(
            station_code="GWL",
            stop_sequence=1,
            day_offset=-1  # Must be >= 0
        )
    assert any("day_offset" in err["loc"] for err in exc_info.value.errors())


def test_train_schedule_entry_empty_station_code():
    with pytest.raises(ValidationError) as exc_info:
        TrainScheduleEntry(
            station_code="   ",
            stop_sequence=1
        )
    assert any("station_code" in err["loc"] for err in exc_info.value.errors())


def test_train_empty_schedule():
    with pytest.raises(ValidationError) as exc_info:
        Train(
            number="12616",
            name="Grand Trunk Express",
            origin_code="GWL",
            destination_code="BPL",
            runs_on_days=[0, 1, 2],
            schedule=[]  # Empty schedule
        )
    assert any("schedule" in err["loc"] for err in exc_info.value.errors())


def test_train_first_station_mismatch(valid_schedule):
    # Origin is GWL, but first schedule station is JHS
    entry1 = TrainScheduleEntry(station_code="JHS", stop_sequence=1)
    entry2 = TrainScheduleEntry(station_code="BPL", stop_sequence=2)

    with pytest.raises(ValidationError) as exc_info:
        Train(
            number="12616",
            name="Grand Trunk Express",
            origin_code="GWL",
            destination_code="BPL",
            runs_on_days=[0, 1, 2],
            schedule=[entry1, entry2]
        )
    assert any("schedule" in err["loc"] for err in exc_info.value.errors())


def test_train_last_station_mismatch(valid_schedule):
    # Destination is BPL, but last schedule station is NGP
    entry1 = TrainScheduleEntry(station_code="GWL", stop_sequence=1)
    entry2 = TrainScheduleEntry(station_code="NGP", stop_sequence=2)

    with pytest.raises(ValidationError) as exc_info:
        Train(
            number="12616",
            name="Grand Trunk Express",
            origin_code="GWL",
            destination_code="BPL",
            runs_on_days=[0, 1, 2],
            schedule=[entry1, entry2]
        )
    assert any("schedule" in err["loc"] for err in exc_info.value.errors())


def test_train_invalid_schedule_not_strictly_increasing():
    entry1 = TrainScheduleEntry(station_code="GWL", stop_sequence=1)
    entry2 = TrainScheduleEntry(station_code="JHS", stop_sequence=2)
    entry3 = TrainScheduleEntry(station_code="BPL", stop_sequence=2)  # Duplicate sequence 2

    with pytest.raises(ValidationError) as exc_info:
        Train(
            number="12616",
            name="Grand Trunk Express",
            origin_code="GWL",
            destination_code="BPL",
            runs_on_days=[0, 1, 2],
            schedule=[entry1, entry2, entry3]
        )
    assert any("schedule" in err["loc"] for err in exc_info.value.errors())


def test_train_invalid_schedule_decreasing():
    entry1 = TrainScheduleEntry(station_code="GWL", stop_sequence=2)
    entry2 = TrainScheduleEntry(station_code="BPL", stop_sequence=1)  # Decreasing sequence

    with pytest.raises(ValidationError) as exc_info:
        Train(
            number="12616",
            name="Grand Trunk Express",
            origin_code="GWL",
            destination_code="BPL",
            runs_on_days=[0, 1, 2],
            schedule=[entry1, entry2]
        )
    assert any("schedule" in err["loc"] for err in exc_info.value.errors())


def test_train_invalid_running_days_out_of_range(valid_schedule):
    with pytest.raises(ValidationError) as exc_info:
        Train(
            number="12616",
            name="Grand Trunk Express",
            origin_code="GWL",
            destination_code="BPL",
            runs_on_days=[0, 1, 7],  # 7 is out of range 0..6
            schedule=valid_schedule
        )
    assert any("runs_on_days" in err["loc"] for err in exc_info.value.errors())


def test_train_invalid_running_days_duplicates(valid_schedule):
    with pytest.raises(ValidationError) as exc_info:
        Train(
            number="12616",
            name="Grand Trunk Express",
            origin_code="GWL",
            destination_code="BPL",
            runs_on_days=[0, 1, 2, 2],  # Duplicate day 2
            schedule=valid_schedule
        )
    assert any("runs_on_days" in err["loc"] for err in exc_info.value.errors())


def test_train_invalid_running_days_empty(valid_schedule):
    with pytest.raises(ValidationError) as exc_info:
        Train(
            number="12616",
            name="Grand Trunk Express",
            origin_code="GWL",
            destination_code="BPL",
            runs_on_days=[],  # Empty
            schedule=valid_schedule
        )
    assert any("runs_on_days" in err["loc"] for err in exc_info.value.errors())
