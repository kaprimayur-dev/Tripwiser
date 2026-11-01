import pytest
import json
import os
import datetime
from pydantic import ValidationError

from app.domain.models.station import Station
from app.domain.models.train import Train, TrainScheduleEntry

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..",
    "app", "infrastructure", "data", "fixtures",
    "bootstrap_railway_data.json"
)


@pytest.fixture(scope="module")
def bootstrap_fixture():
    assert os.path.exists(FIXTURE_PATH), f"Fixture not found at {FIXTURE_PATH}"
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# =====================================================================
# A. STATIONS DOMAIN VALIDATION TESTS
# =====================================================================

def test_fixture_stations_valid_domain(bootstrap_fixture):
    """Test that all 50 stations in the fixture deserialize into valid Station domain models."""
    stations_data = bootstrap_fixture["stations"]
    assert len(stations_data) == 50

    seen_codes = set()
    for s in stations_data:
        stn = Station(
            code=s["code"],
            name=s["name"],
            latitude=s["latitude"],
            longitude=s["longitude"],
            state=s.get("state"),
            zone=s.get("zone")
        )
        assert stn.code == s["code"]
        assert -90.0 <= stn.latitude <= 90.0
        assert -180.0 <= stn.longitude <= 180.0
        assert not (stn.latitude == 0.0 and stn.longitude == 0.0), f"Dummy (0,0) found in {stn.code}"
        assert stn.code not in seen_codes, f"Duplicate station code {stn.code}"
        seen_codes.add(stn.code)


def test_station_latitude_boundaries():
    """Verify station rejects invalid latitude."""
    with pytest.raises(ValidationError) as exc_info:
        Station(code="TEST", name="Test Station", latitude=91.0, longitude=77.0)
    assert "latitude" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        Station(code="TEST", name="Test Station", latitude=-90.5, longitude=77.0)
    assert "latitude" in str(exc_info.value)


def test_station_longitude_boundaries():
    """Verify station rejects invalid longitude."""
    with pytest.raises(ValidationError) as exc_info:
        Station(code="TEST", name="Test Station", latitude=20.0, longitude=180.5)
    assert "longitude" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        Station(code="TEST", name="Test Station", latitude=20.0, longitude=-181.0)
    assert "longitude" in str(exc_info.value)


def test_station_duplicate_detection(bootstrap_fixture):
    """Verify detection of duplicate station codes in a collection."""
    stations_data = bootstrap_fixture["stations"]
    codes = [s["code"] for s in stations_data]
    assert len(codes) == len(set(codes)), "Fixture contains duplicate station codes"


def test_station_coordinate_taxonomy(bootstrap_fixture):
    """
    Verify strict coordinate taxonomy:
    - 50 stations have coordinates present and structurally validated.
    - Exactly 5 landmark stations are INDEPENDENTLY_VERIFIED with benchmark sources and URLs.
    - Exactly 45 stations are NOT_INDEPENDENTLY_VERIFIED.
    """
    stations_data = bootstrap_fixture["stations"]
    assert len(stations_data) == 50

    independently_verified_count = 0
    not_independently_verified_count = 0

    expected_verified_codes = {"NDLS", "HWH", "MMCT", "CSMT", "MAS"}

    for s in stations_data:
        assert s["coordinates_present"] is True
        assert s["structurally_validated"] is True
        status = s["coordinate_validation_status"]
        if status == "INDEPENDENTLY_VERIFIED":
            independently_verified_count += 1
            assert s["code"] in expected_verified_codes
            assert "independent_source" in s and len(s["independent_source"]) > 0
            assert "independent_source_url" in s and s["independent_source_url"].startswith("http")
        elif status == "NOT_INDEPENDENTLY_VERIFIED":
            not_independently_verified_count += 1
        else:
            pytest.fail(f"Unexpected coordinate status {status} for station {s['code']}")

    assert independently_verified_count == 5
    assert not_independently_verified_count == 45


# =====================================================================
# B. ACTIVE TRAINS DOMAIN VALIDATION TESTS
# =====================================================================

def test_fixture_active_trains_valid_domain(bootstrap_fixture):
    """
    Test that all 12 active ROUTE_TABLE_VERIFIED trains in the fixture deserialize into valid Train domain models.
    Ensures no default distance_km or day_offset fallbacks are used.
    """
    trains_data = bootstrap_fixture["trains"]
    assert len(trains_data) == 12, "Expected exactly 12 active verified trains"

    for t in trains_data:
        assert t["verification_status"] == "ROUTE_TABLE_VERIFIED"
        schedule_entries = []
        for entry in t["schedule"]:
            # Explicit lookup without fallback defaults to prevent invented values
            sch = TrainScheduleEntry(
                station_code=entry["station_code"],
                arrival_time=entry.get("arrival_time"),
                departure_time=entry.get("departure_time"),
                day_offset=entry["day_offset"],
                distance_km=entry["distance_km"],
                stop_sequence=entry["stop_sequence"]
            )
            schedule_entries.append(sch)

        trn = Train(
            number=t["number"],
            name=t["name"],
            origin_code=t["origin_code"],
            destination_code=t["destination_code"],
            runs_on_days=t["runs_on_days"],
            schedule=schedule_entries
        )
        assert trn.number == t["number"]
        assert isinstance(trn.number, str)
        assert trn.origin_code == schedule_entries[0].station_code
        assert trn.destination_code == schedule_entries[-1].station_code
        assert len(trn.runs_on_days) > 0


def test_fixture_active_trains_provenance(bootstrap_fixture):
    """
    Verify provenance metadata for every active verified train:
    - Official timetable source URL.
    - Document name.
    - Table number including sub-table identifier.
    - PDF page number.
    - Verified fields list.
    """
    trains_data = bootstrap_fixture["trains"]
    for t in trains_data:
        assert t["source_url"].startswith("https://rb.indianrailways.gov.in/")
        assert t["source_document"].endswith(".pdf")
        assert len(t["source_table"]) > 0
        assert isinstance(t["source_page"], int) and t["source_page"] >= 1
        assert len(t["verified_fields"]) > 0
        assert "number" in t["verified_fields"]
        assert "table_number" in t["verified_fields"]


def test_train_references_collection_integrity(bootstrap_fixture):
    """
    Verify separate train_references collection:
    - Contains exactly 8 reference records (6 INDEX_VERIFIED, 2 SOURCE_CONFLICT).
    - Contains NO intermediate schedule halts, invented dwell times, or distances.
    - Source-conflict records contain candidate endpoints and conflict citations.
    - No source-conflict or index-verified train is present in active trains collection.
    """
    active_numbers = {t["number"] for t in bootstrap_fixture["trains"]}
    references = bootstrap_fixture["train_references"]
    assert len(references) == 8

    index_verified = [r for r in references if r["verification_status"] == "INDEX_VERIFIED"]
    source_conflict = [r for r in references if r["verification_status"] == "SOURCE_CONFLICT"]

    assert len(index_verified) == 6
    assert len(source_conflict) == 2

    # Assert no overlap with active usable trains
    ref_numbers = {r["number"] for r in references}
    assert active_numbers.isdisjoint(ref_numbers)

    # Assert references do NOT retain complete/invented schedules
    for r in references:
        assert "schedule" not in r, f"Reference record {r['number']} must not contain schedule"
        assert r["source_url"].startswith("https://rb.indianrailways.gov.in/")
        assert r["source_document"] == "TableNumberIndex.pdf"

    # Assert SOURCE_CONFLICT records explicitly document conflict evidence
    for sc in source_conflict:
        assert sc["number"] in ["12615", "12616"]
        assert "candidate_endpoints" in sc
        assert len(sc["candidate_endpoints"]) >= 3
        assert "conflict_citations" in sc
        assert len(sc["conflict_citations"]) >= 4


def test_train_number_preserved_as_string_with_leading_zero():
    """Train numbers with leading zeroes must be preserved as strings."""
    sch = [
        TrainScheduleEntry(station_code="NDLS", departure_time=datetime.time(10, 0), day_offset=0, stop_sequence=1),
        TrainScheduleEntry(station_code="AGC", arrival_time=datetime.time(12, 0), day_offset=0, stop_sequence=2)
    ]
    trn = Train(
        number="04601",
        name="Special Express",
        origin_code="NDLS",
        destination_code="AGC",
        runs_on_days=[0, 3],
        schedule=sch
    )
    assert trn.number == "04601"
    assert isinstance(trn.number, str)
    assert trn.number.startswith("0")


def test_train_running_days_validation():
    """Train must validate running days are between 0 and 6, non-empty, and without duplicates."""
    sch = [
        TrainScheduleEntry(station_code="NDLS", departure_time=datetime.time(10, 0), day_offset=0, stop_sequence=1),
        TrainScheduleEntry(station_code="AGC", arrival_time=datetime.time(12, 0), day_offset=0, stop_sequence=2)
    ]
    # Invalid day > 6
    with pytest.raises(ValidationError):
        Train(number="12345", name="Test", origin_code="NDLS", destination_code="AGC", runs_on_days=[0, 7], schedule=sch)

    # Empty running days
    with pytest.raises(ValidationError):
        Train(number="12345", name="Test", origin_code="NDLS", destination_code="AGC", runs_on_days=[], schedule=sch)

    # Duplicate running days
    with pytest.raises(ValidationError):
        Train(number="12345", name="Test", origin_code="NDLS", destination_code="AGC", runs_on_days=[1, 1, 3], schedule=sch)


# =====================================================================
# C. TRAIN SCHEDULE & ORDERING INTEGRITY TESTS
# =====================================================================

def test_schedule_stop_sequence_monotonicity():
    """Stop sequences must be strictly increasing."""
    sch_invalid = [
        TrainScheduleEntry(station_code="NDLS", departure_time=datetime.time(10, 0), day_offset=0, stop_sequence=1),
        TrainScheduleEntry(station_code="MTJ", arrival_time=datetime.time(11, 0), departure_time=datetime.time(11, 5), day_offset=0, stop_sequence=3),
        TrainScheduleEntry(station_code="AGC", arrival_time=datetime.time(12, 0), day_offset=0, stop_sequence=2)  # Decreasing sequence
    ]
    with pytest.raises(ValidationError) as exc_info:
        Train(number="12345", name="Test", origin_code="NDLS", destination_code="AGC", runs_on_days=[0], schedule=sch_invalid)
    assert "strictly increasing" in str(exc_info.value)


def test_schedule_cumulative_distance_monotonicity(bootstrap_fixture):
    """Cumulative distances in active verified train schedules must be non-decreasing."""
    for t in bootstrap_fixture["trains"]:
        sch = t["schedule"]
        for i in range(len(sch) - 1):
            d1 = sch[i]["distance_km"]
            d2 = sch[i + 1]["distance_km"]
            assert d1 <= d2, f"Train {t['number']} distance regression: {d1} > {d2} at stop {sch[i+1]['station_code']}"


def test_schedule_origin_destination_agreement():
    """First and last schedule entry must agree with train origin and destination."""
    sch = [
        TrainScheduleEntry(station_code="NDLS", departure_time=datetime.time(10, 0), day_offset=0, stop_sequence=1),
        TrainScheduleEntry(station_code="AGC", arrival_time=datetime.time(12, 0), day_offset=0, stop_sequence=2)
    ]
    with pytest.raises(ValidationError) as exc_info:
        Train(number="12345", name="Test", origin_code="HWH", destination_code="AGC", runs_on_days=[0], schedule=sch)
    assert "origin_code" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        Train(number="12345", name="Test", origin_code="NDLS", destination_code="BPL", runs_on_days=[0], schedule=sch)
    assert "destination_code" in str(exc_info.value)


# =====================================================================
# D. CONCRETE OVERNIGHT JOURNEY & TEMPORAL TESTS
# =====================================================================

def test_concrete_overnight_journey_scenario():
    """
    Test the exact concrete scenario requested by the CTO:
    Origin: Departure Day 1 - 23:40
    Intermediate: Arrival Day 1 - 23:55, Departure Day 2 - 00:05
    Next station: Arrival Day 2 - 02:30, Departure Day 2 - 02:35
    Terminal: Arrival Day 2 - 06:15, No departure
    """
    sch = [
        TrainScheduleEntry(
            station_code="NDLS",
            arrival_time=None,
            departure_time=datetime.time(23, 40),
            day_offset=0,
            distance_km=0.0,
            stop_sequence=1
        ),
        TrainScheduleEntry(
            station_code="MTJ",
            arrival_time=datetime.time(23, 55),
            departure_time=datetime.time(0, 5),
            day_offset=1,
            distance_km=141.0,
            stop_sequence=2
        ),
        TrainScheduleEntry(
            station_code="AGC",
            arrival_time=datetime.time(2, 30),
            departure_time=datetime.time(2, 35),
            day_offset=1,
            distance_km=195.0,
            stop_sequence=3
        ),
        TrainScheduleEntry(
            station_code="GWL",
            arrival_time=datetime.time(6, 15),
            departure_time=None,
            day_offset=1,
            distance_km=313.0,
            stop_sequence=4
        )
    ]

    trn = Train(
        number="SYN901",
        name="Synthetic Overnight Express",
        origin_code="NDLS",
        destination_code="GWL",
        runs_on_days=[0, 1, 2, 3, 4, 5, 6],
        schedule=sch
    )

    assert trn.schedule[0].arrival_time is None
    assert trn.schedule[0].departure_time == datetime.time(23, 40)
    assert trn.schedule[0].day_offset == 0

    assert trn.schedule[1].arrival_time == datetime.time(23, 55)
    assert trn.schedule[1].departure_time == datetime.time(0, 5)
    assert trn.schedule[1].day_offset == 1
    assert trn.schedule[1].arrival_time > trn.schedule[1].departure_time

    assert trn.schedule[2].arrival_time == datetime.time(2, 30)
    assert trn.schedule[2].departure_time == datetime.time(2, 35)
    assert trn.schedule[2].day_offset == 1

    assert trn.schedule[3].arrival_time == datetime.time(6, 15)
    assert trn.schedule[3].departure_time is None
    assert trn.schedule[3].day_offset == 1


def test_schedule_missing_origin_arrival():
    """Verify that an origin schedule entry has arrival_time as None and valid departure_time."""
    entry = TrainScheduleEntry(
        station_code="NDLS",
        arrival_time=None,
        departure_time=datetime.time(16, 55),
        day_offset=0,
        distance_km=0.0,
        stop_sequence=1
    )
    assert entry.arrival_time is None
    assert entry.departure_time == datetime.time(16, 55)
    assert entry.day_offset == 0


def test_schedule_missing_terminal_departure():
    """Verify that a terminal schedule entry has departure_time as None and valid arrival_time."""
    entry = TrainScheduleEntry(
        station_code="MMCT",
        arrival_time=datetime.time(8, 35),
        departure_time=None,
        day_offset=1,
        distance_km=1386.0,
        stop_sequence=7
    )
    assert entry.arrival_time == datetime.time(8, 35)
    assert entry.departure_time is None
    assert entry.day_offset == 1


def _is_valid_schedule_halt_filter(arrival: datetime.time | None, departure: datetime.time | None) -> bool:
    """Pure validation rule defining valid halt criteria for the ingestion pipeline filter."""
    return not (arrival is None and departure is None)


def test_schedule_missing_arrival_and_departure_ingestion_filter_rule():
    """
    Specification Test for Future Ingestion Filter Requirement:
    An intermediate halt missing BOTH arrival and departure times is invalid
    and must be rejected by the validation filter during future ingestion.
    Note: Tests the pure validation rule specification; the operational quarantine
    subsystem itself belongs to the TW-103B ingestion pipeline.
    """
    assert _is_valid_schedule_halt_filter(None, None) is False
    assert _is_valid_schedule_halt_filter(datetime.time(10, 0), None) is True
    assert _is_valid_schedule_halt_filter(None, datetime.time(10, 5)) is True
    assert _is_valid_schedule_halt_filter(datetime.time(10, 0), datetime.time(10, 5)) is True


def test_schedule_negative_day_offset_rejected():
    """Negative day offsets must be rejected by Pydantic ge=0 constraint."""
    with pytest.raises(ValidationError) as exc_info:
        TrainScheduleEntry(
            station_code="NDLS",
            departure_time=datetime.time(10, 0),
            day_offset=-1,
            stop_sequence=1
        )
    assert "day_offset" in str(exc_info.value)


def test_multi_day_journey():
    """Multi-day journey across 3 days increments day_offset monotonically."""
    sch = [
        TrainScheduleEntry(station_code="NDLS", departure_time=datetime.time(16, 10), day_offset=0, stop_sequence=1),
        TrainScheduleEntry(station_code="BPL", arrival_time=datetime.time(2, 0), departure_time=datetime.time(2, 10), day_offset=1, stop_sequence=2),
        TrainScheduleEntry(station_code="MAS", arrival_time=datetime.time(6, 20), departure_time=None, day_offset=2, stop_sequence=3)
    ]
    trn = Train(
        number="SYN902",
        name="Synthetic Multi-Day Express",
        origin_code="NDLS",
        destination_code="MAS",
        runs_on_days=[0, 1, 2, 3, 4, 5, 6],
        schedule=sch
    )
    assert trn.schedule[0].day_offset == 0
    assert trn.schedule[1].day_offset == 1
    assert trn.schedule[2].day_offset == 2


# =====================================================================
# E. CROSS-FIXTURE REFERENTIAL INTEGRITY TESTS
# =====================================================================

def test_cross_fixture_referential_integrity(bootstrap_fixture):
    """
    Verifies full referential integrity between trains, references, and stations:
    - 50 unique stations exist.
    - Exactly 12 active verified trains, all with valid route schedules.
    - Exactly 8 reference trains in separate train_references collection.
    - Total 20 distinct train numbers across collections.
    - Every active train origin and destination exists in station fixture.
    - Every active schedule stop exists in station fixture.
    - Stop sequences are unique and strictly increasing.
    - First and last schedule stops match train endpoints.
    - Distances are non-decreasing.
    """
    stations = bootstrap_fixture["stations"]
    active_trains = bootstrap_fixture["trains"]
    train_references = bootstrap_fixture["train_references"]

    station_codes = {s["code"] for s in stations}
    assert len(station_codes) == 50, "Expected exactly 50 unique stations"

    active_numbers = [t["number"] for t in active_trains]
    ref_numbers = [r["number"] for r in train_references]
    assert len(active_numbers) == 12
    assert len(ref_numbers) == 8
    all_numbers = active_numbers + ref_numbers
    assert len(all_numbers) == len(set(all_numbers)), "Duplicate train numbers found across collections"

    schedule_station_codes = set()
    for t in active_trains:
        origin = t["origin_code"]
        dest = t["destination_code"]
        assert origin in station_codes, f"Train {t['number']} origin {origin} not in station fixture"
        assert dest in station_codes, f"Train {t['number']} destination {dest} not in station fixture"

        sch = t["schedule"]
        assert len(sch) >= 2, f"Train {t['number']} schedule has fewer than 2 stops"
        assert sch[0]["station_code"] == origin, f"Train {t['number']} first stop != origin"
        assert sch[-1]["station_code"] == dest, f"Train {t['number']} last stop != destination"

        seqs = [s["stop_sequence"] for s in sch]
        assert len(seqs) == len(set(seqs)), f"Train {t['number']} has duplicate stop sequences"
        assert seqs == sorted(seqs), f"Train {t['number']} stop sequences not sorted"
        for i in range(len(seqs) - 1):
            assert seqs[i] < seqs[i + 1], f"Train {t['number']} stop sequence not strictly increasing"

        dists = [s["distance_km"] for s in sch]
        for i in range(len(dists) - 1):
            assert dists[i] <= dists[i + 1], f"Train {t['number']} distance regression"

        for s in sch:
            c = s["station_code"]
            schedule_station_codes.add(c)
            assert c in station_codes, f"Schedule station code {c} not in station fixture"

    assert len(schedule_station_codes) <= len(station_codes)
    assert schedule_station_codes.issubset(station_codes)
