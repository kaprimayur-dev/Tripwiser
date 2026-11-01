import datetime
from pathlib import Path
from dataclasses import FrozenInstanceError
from types import MappingProxyType
import pytest

from app.domain.models.station import Station
from app.domain.models.train import Train, TrainScheduleEntry
from app.infrastructure.adapters.datameet.station_adapter import DataMeetStationAdapter
from app.infrastructure.adapters.datameet.models import (
    AdapterResult,
    AcceptedRecord,
    QuarantineRecord,
    SourceProvenance,
)
from app.infrastructure.adapters.datameet.train_adapter import DataMeetTrainAdapter
from app.infrastructure.adapters.datameet.train_models import (
    DataMeetTrainRecord,
    TrainAdapterResult,
    AcceptedTrainRecord,
    TrainQuarantineRecord,
)
from app.infrastructure.adapters.datameet.schedule_adapter import DataMeetScheduleAdapter
from app.infrastructure.adapters.datameet.schedule_models import (
    DataMeetScheduleEntry,
    DataMeetTrainSchedule,
    ScheduleAdapterResult,
    AcceptedScheduleRecord,
    ScheduleQuarantineRecord,
)
from app.infrastructure.integration.models import (
    IntegratedScheduleStop,
    IntegratedTrainSchedule,
    IntegratedTrainRecord,
    IntegratedRailwayDataset,
)
from app.infrastructure.integration.calendar_provider import (
    DictCalendarProvider,
    FixtureCalendarProvider,
)
from app.infrastructure.integration.service import RailwayDataIntegrationService

STATIONS_PATH = Path("app/infrastructure/data/sources/datameet/stations.json")
TRAINS_PATH = Path("app/infrastructure/data/sources/datameet/trains.json")
SCHEDULES_PATH = Path("app/infrastructure/data/sources/datameet/schedules.json")
BOOTSTRAP_FIXTURE_PATH = Path("app/infrastructure/data/fixtures/bootstrap_railway_data.json")


def _make_station(code: str, name: str, lat: float = 28.61, lon: float = 77.23) -> Station:
    return Station(code=code, name=name, latitude=lat, longitude=lon)


def _make_train_header(
    number: str = "12951",
    name: str = "Mumbai Rajdhani",
    origin_code: str = "MMCT",
    destination_code: str = "NDLS",
) -> DataMeetTrainRecord:
    return DataMeetTrainRecord(
        number=number,
        name=name,
        origin_code=origin_code,
        destination_code=destination_code,
    )


def _make_schedule_entry(
    record_id: int,
    train_number: str,
    station_code: str,
    stop_sequence: int,
    arrival: datetime.time | None = None,
    departure: datetime.time | None = None,
    day: int | None = 1,
    day_offset: int | None = 0,
    is_timing_complete: bool = True,
    warnings: tuple[str, ...] = (),
) -> DataMeetScheduleEntry:
    return DataMeetScheduleEntry(
        source_record_id=record_id,
        train_number=train_number,
        station_code=station_code,
        stop_sequence=stop_sequence,
        arrival_time=arrival,
        departure_time=departure,
        day=day,
        day_offset=day_offset,
        is_timing_complete=is_timing_complete,
        validation_warnings=warnings,
    )


class TestRailwayDataIntegrationServiceUnit:
    """Verifies reference resolution, sequencing, Tier 1 preservation, and Tier 2 compilation."""

    def test_successful_integration_and_domain_compilation(self):
        # 1. Stations
        stn1 = _make_station("MMCT", "Mumbai Central", 18.96, 72.81)
        stn2 = _make_station("NDLS", "New Delhi", 28.64, 77.22)
        station_result = AdapterResult(
            records=(stn1, stn2),
            accepted=(),
            quarantined=(),
            provenance=SourceProvenance(),
        )

        # 2. Train Header
        header = _make_train_header("12951", "Mumbai Rajdhani", "MMCT", "NDLS")
        train_result = TrainAdapterResult(
            records=(header,),
            accepted=(),
            quarantined=(),
            provenance=SourceProvenance(),
        )

        # 3. Schedule
        stop1 = _make_schedule_entry(100, "12951", "MMCT", 1, departure=datetime.time(16, 35), day=1, day_offset=0)
        stop2 = _make_schedule_entry(200, "12951", "NDLS", 2, arrival=datetime.time(8, 35), day=2, day_offset=1)
        sched = DataMeetTrainSchedule(
            train_number="12951",
            train_name="Mumbai Rajdhani",
            origin_code="MMCT",
            destination_code="NDLS",
            total_stops=2,
            entries=(stop1, stop2),
        )
        schedule_result = ScheduleAdapterResult(
            train_schedules=(sched,),
            records=(stop1, stop2),
            accepted=(),
            quarantined=(),
            provenance=SourceProvenance(),
        )

        # 4. Calendar Provider
        calendar = DictCalendarProvider({"12951": [0, 1, 2, 3, 4, 5, 6]})

        service = RailwayDataIntegrationService()
        dataset = service.integrate(
            stations_source=station_result,
            trains_source=train_result,
            schedules_source=schedule_result,
            calendar_provider=calendar,
        )

        # Tier 1 checks
        assert len(dataset.stations) == 2
        assert len(dataset.train_records) == 1
        assert len(dataset.train_schedules) == 1
        assert len(dataset.schedule_stops) == 2

        int_stop1 = dataset.schedule_stops[0]
        assert int_stop1.station == stn1
        assert int_stop1.stop_sequence == 1
        assert int_stop1.day_offset == 0

        int_stop2 = dataset.schedule_stops[1]
        assert int_stop2.station == stn2
        assert int_stop2.stop_sequence == 2
        assert int_stop2.day_offset == 1

        # Tier 2 checks: fully qualified for TW-102 Train
        assert len(dataset.compiled_trains) == 1
        compiled = dataset.compiled_trains[0]
        assert isinstance(compiled, Train)
        assert compiled.number == "12951"
        assert compiled.origin_code == "MMCT"
        assert compiled.destination_code == "NDLS"
        assert compiled.runs_on_days == [0, 1, 2, 3, 4, 5, 6]
        assert len(compiled.schedule) == 2
        assert compiled.schedule[0].station_code == "MMCT"
        assert compiled.schedule[1].station_code == "NDLS"

        # Record flags
        rec = dataset.train_records[0]
        assert rec.is_compilable_to_domain is True
        assert rec.uncompilable_reasons == ()
        assert len(dataset.uncompiled_trains) == 0

    def test_missing_running_calendar_retains_train_in_tier_1_as_uncompiled(self):
        stn1 = _make_station("MMCT", "Mumbai Central")
        stn2 = _make_station("NDLS", "New Delhi")
        station_result = AdapterResult(records=(stn1, stn2), accepted=(), quarantined=(), provenance=SourceProvenance())
        header = _make_train_header("12951", "Mumbai Rajdhani", "MMCT", "NDLS")
        train_result = TrainAdapterResult(records=(header,), accepted=(), quarantined=(), provenance=SourceProvenance())
        stop1 = _make_schedule_entry(100, "12951", "MMCT", 1, departure=datetime.time(16, 35), day_offset=0)
        stop2 = _make_schedule_entry(200, "12951", "NDLS", 2, arrival=datetime.time(8, 35), day_offset=1)
        sched = DataMeetTrainSchedule(
            train_number="12951", train_name="Mumbai Rajdhani", origin_code="MMCT", destination_code="NDLS",
            total_stops=2, entries=(stop1, stop2),
        )
        schedule_result = ScheduleAdapterResult(
            train_schedules=(sched,), records=(stop1, stop2), accepted=(), quarantined=(), provenance=SourceProvenance()
        )

        service = RailwayDataIntegrationService()
        # No calendar provider supplied
        dataset = service.integrate(
            stations_source=station_result,
            trains_source=train_result,
            schedules_source=schedule_result,
            calendar_provider=None,
        )

        # Tier 1 preserves the train
        assert len(dataset.train_records) == 1
        rec = dataset.train_records[0]
        assert rec.is_compilable_to_domain is False
        assert "AWAITING_RUNNING_CALENDAR" in rec.uncompilable_reasons

        # Tier 2 does NOT fabricate running days
        assert len(dataset.compiled_trains) == 0
        assert len(dataset.uncompiled_trains) == 1

    def test_unknown_day_offset_preserves_none_and_blocks_compilation(self):
        stn1 = _make_station("MMCT", "Mumbai Central")
        stn2 = _make_station("NDLS", "New Delhi")
        station_result = AdapterResult(records=(stn1, stn2), accepted=(), quarantined=(), provenance=SourceProvenance())
        header = _make_train_header("12951", "Mumbai Rajdhani", "MMCT", "NDLS")
        train_result = TrainAdapterResult(records=(header,), accepted=(), quarantined=(), provenance=SourceProvenance())

        # Stop 2 has day=None and day_offset=None
        stop1 = _make_schedule_entry(100, "12951", "MMCT", 1, departure=datetime.time(16, 35), day=1, day_offset=0)
        stop2 = _make_schedule_entry(200, "12951", "NDLS", 2, arrival=datetime.time(8, 35), day=None, day_offset=None, warnings=("MISSING_DAY_FIELD",))
        sched = DataMeetTrainSchedule(
            train_number="12951", train_name="Mumbai Rajdhani", origin_code="MMCT", destination_code="NDLS",
            total_stops=2, entries=(stop1, stop2),
        )
        schedule_result = ScheduleAdapterResult(
            train_schedules=(sched,), records=(stop1, stop2), accepted=(), quarantined=(), provenance=SourceProvenance()
        )

        calendar = DictCalendarProvider({"12951": [0, 1, 2, 3, 4, 5, 6]})
        service = RailwayDataIntegrationService()
        dataset = service.integrate(
            stations_source=station_result,
            trains_source=train_result,
            schedules_source=schedule_result,
            calendar_provider=calendar,
        )

        # Tier 1 strictly preserves day_offset=None without zero-defaulting
        assert dataset.schedule_stops[1].day_offset is None
        assert dataset.schedule_stops[1].day is None

        # Blocked from TW-102 Train compilation
        assert len(dataset.compiled_trains) == 0
        assert len(dataset.uncompiled_trains) == 1
        assert "UNKNOWN_DAY_OFFSET" in dataset.uncompiled_trains[0].uncompilable_reasons

    def test_endpoint_mismatch_blocks_compilation_and_retains_warnings(self):
        stn1 = _make_station("MMCT", "Mumbai Central")
        stn2 = _make_station("BVI", "Borivali")
        stn3 = _make_station("NDLS", "New Delhi")
        station_result = AdapterResult(records=(stn1, stn2, stn3), accepted=(), quarantined=(), provenance=SourceProvenance())

        # Header says MMCT -> NDLS, but schedule first stop is BVI
        header = _make_train_header("12951", "Mumbai Rajdhani", "MMCT", "NDLS")
        train_result = TrainAdapterResult(records=(header,), accepted=(), quarantined=(), provenance=SourceProvenance())

        stop1 = _make_schedule_entry(100, "12951", "BVI", 1, departure=datetime.time(17, 0), day_offset=0)
        stop2 = _make_schedule_entry(200, "12951", "NDLS", 2, arrival=datetime.time(8, 35), day_offset=1)
        sched = DataMeetTrainSchedule(
            train_number="12951", train_name="Mumbai Rajdhani", origin_code="BVI", destination_code="NDLS",
            total_stops=2, entries=(stop1, stop2), schedule_warnings=("ORIGIN_STATION_MISMATCH",),
        )
        schedule_result = ScheduleAdapterResult(
            train_schedules=(sched,), records=(stop1, stop2), accepted=(), quarantined=(), provenance=SourceProvenance()
        )

        calendar = DictCalendarProvider({"12951": [0, 1, 2, 3, 4, 5, 6]})
        service = RailwayDataIntegrationService()
        dataset = service.integrate(
            stations_source=station_result,
            trains_source=train_result,
            schedules_source=schedule_result,
            calendar_provider=calendar,
        )

        assert len(dataset.compiled_trains) == 0
        rec = dataset.uncompiled_trains[0]
        assert "ORIGIN_ENDPOINT_MISMATCH" in rec.uncompilable_reasons
        assert "ORIGIN_STATION_MISMATCH" in rec.schedule.schedule_warnings

    def test_incomplete_timing_preserves_topology_and_blocks_compilation(self):
        stn1 = _make_station("MMCT", "Mumbai Central")
        stn2 = _make_station("NDLS", "New Delhi")
        station_result = AdapterResult(records=(stn1, stn2), accepted=(), quarantined=(), provenance=SourceProvenance())
        header = _make_train_header("12951", "Mumbai Rajdhani", "MMCT", "NDLS")
        train_result = TrainAdapterResult(records=(header,), accepted=(), quarantined=(), provenance=SourceProvenance())

        stop1 = _make_schedule_entry(100, "12951", "MMCT", 1, arrival=None, departure=None, day_offset=0, is_timing_complete=False)
        stop2 = _make_schedule_entry(200, "12951", "NDLS", 2, arrival=datetime.time(8, 35), day_offset=1)
        sched = DataMeetTrainSchedule(
            train_number="12951", train_name="Mumbai Rajdhani", origin_code="MMCT", destination_code="NDLS",
            total_stops=2, entries=(stop1, stop2),
        )
        schedule_result = ScheduleAdapterResult(
            train_schedules=(sched,), records=(stop1, stop2), accepted=(), quarantined=(), provenance=SourceProvenance()
        )

        calendar = DictCalendarProvider({"12951": [0, 1, 2, 3, 4, 5, 6]})
        service = RailwayDataIntegrationService()
        dataset = service.integrate(
            stations_source=station_result,
            trains_source=train_result,
            schedules_source=schedule_result,
            calendar_provider=calendar,
        )

        # Tier 1 preserves topology with is_timing_complete=False
        assert dataset.schedule_stops[0].is_timing_complete is False
        assert len(dataset.compiled_trains) == 0
        assert "INCOMPLETE_TIMING" in dataset.uncompiled_trains[0].uncompilable_reasons

    def test_unlocated_station_reference_excluded_from_integrated_schedule(self):
        # Station MMCT is accepted, but station UNK is missing from accepted stations
        stn1 = _make_station("MMCT", "Mumbai Central")
        station_result = AdapterResult(records=(stn1,), accepted=(), quarantined=(), provenance=SourceProvenance())
        header = _make_train_header("12951", "Mumbai Rajdhani", "MMCT", "NDLS")
        train_result = TrainAdapterResult(records=(header,), accepted=(), quarantined=(), provenance=SourceProvenance())

        stop1 = _make_schedule_entry(100, "12951", "MMCT", 1, departure=datetime.time(16, 35), day_offset=0)
        stop2 = _make_schedule_entry(200, "12951", "UNK", 2, arrival=datetime.time(8, 35), day_offset=1)
        sched = DataMeetTrainSchedule(
            train_number="12951", train_name="Mumbai Rajdhani", origin_code="MMCT", destination_code="NDLS",
            total_stops=2, entries=(stop1, stop2),
        )
        schedule_result = ScheduleAdapterResult(
            train_schedules=(sched,), records=(stop1, stop2), accepted=(), quarantined=(), provenance=SourceProvenance()
        )

        service = RailwayDataIntegrationService()
        dataset = service.integrate(
            stations_source=station_result,
            trains_source=train_result,
            schedules_source=schedule_result,
        )

        # UNK was not resolved in station_map, so it was excluded from integrated stops
        assert len(dataset.schedule_stops) == 1
        assert dataset.schedule_stops[0].station_code == "MMCT"

    def test_compilation_exclusion_reasons_multiple_accumulated(self):
        # Train has missing calendar AND endpoint mismatch AND incomplete timing
        stn1 = _make_station("MMCT", "Mumbai Central")
        stn2 = _make_station("BVI", "Borivali")
        station_result = AdapterResult(records=(stn1, stn2), accepted=(), quarantined=(), provenance=SourceProvenance())
        header = _make_train_header("12951", "Mumbai Rajdhani", "MMCT", "NDLS")
        train_result = TrainAdapterResult(records=(header,), accepted=(), quarantined=(), provenance=SourceProvenance())

        # First stop BVI (mismatch), last stop BVI (mismatch), arrival/departure None (incomplete timing), day None (unknown day offset)
        stop1 = _make_schedule_entry(100, "12951", "BVI", 1, arrival=None, departure=None, day=None, day_offset=None, is_timing_complete=False)
        sched = DataMeetTrainSchedule(
            train_number="12951", train_name="Mumbai Rajdhani", origin_code="BVI", destination_code="BVI",
            total_stops=1, entries=(stop1,),
        )
        schedule_result = ScheduleAdapterResult(
            train_schedules=(sched,), records=(stop1,), accepted=(), quarantined=(), provenance=SourceProvenance()
        )

        service = RailwayDataIntegrationService()
        dataset = service.integrate(
            stations_source=station_result,
            trains_source=train_result,
            schedules_source=schedule_result,
            calendar_provider=None,  # No calendar
        )

        rec = dataset.uncompiled_trains[0]
        assert "AWAITING_RUNNING_CALENDAR" in rec.uncompilable_reasons
        assert "UNKNOWN_DAY_OFFSET" in rec.uncompilable_reasons
        assert "ORIGIN_ENDPOINT_MISMATCH" in rec.uncompilable_reasons
        assert "DESTINATION_ENDPOINT_MISMATCH" in rec.uncompilable_reasons
        assert "INCOMPLETE_TIMING" in rec.uncompilable_reasons

    def test_calendar_provider_implementations(self, tmp_path):
        dict_provider = DictCalendarProvider({" 12951 ": [0, 1, 2, 3, 4, 5, 6]})
        assert dict_provider.get_running_days("12951") == (0, 1, 2, 3, 4, 5, 6)
        assert dict_provider.get_running_days("UNKNOWN") is None

        missing_fixture = tmp_path / "non_existent.json"
        fixture_provider = FixtureCalendarProvider(missing_fixture)
        assert fixture_provider.get_running_days("12951") is None

    def test_immutability_and_collection_normalization(self):
        stn1 = _make_station("MMCT", "Mumbai Central")
        stop = IntegratedScheduleStop(
            source_record_id=1,
            train_number="12951",
            station_code="MMCT",
            stop_sequence=1,
            station=stn1,
            validation_warnings=["WARN1"],
        )
        assert isinstance(stop.validation_warnings, tuple)
        with pytest.raises(FrozenInstanceError):
            stop.stop_sequence = 2  # type: ignore

        sched = IntegratedTrainSchedule(
            train_number="12951",
            train_name="Rajdhani",
            origin_station=stn1,
            destination_station=stn1,
            total_stops=1,
            stops=[stop],
            schedule_warnings=["SCHED_WARN"],
        )
        assert isinstance(sched.stops, tuple)
        assert isinstance(sched.schedule_warnings, tuple)
        with pytest.raises(FrozenInstanceError):
            sched.total_stops = 5  # type: ignore

        with pytest.raises(TypeError):
            # stops cannot be scalar
            IntegratedTrainSchedule(
                train_number="12951",
                train_name="Rajdhani",
                origin_station=stn1,
                destination_station=stn1,
                total_stops=1,
                stops=stop,  # type: ignore
            )


@pytest.mark.skipif(not SCHEDULES_PATH.exists(), reason="Requires full local dataset snapshot")
class TestRailwayDataIntegrationServiceEndToEnd:
    """Verifies end-to-end integration across stations.json, trains.json, schedules.json, and bootstrap fixture."""

    def test_full_pipeline_dataset_reconciliation(self):
        service = RailwayDataIntegrationService()
        calendar_provider = FixtureCalendarProvider(BOOTSTRAP_FIXTURE_PATH)

        dataset = service.integrate(
            stations_source=STATIONS_PATH,
            trains_source=TRAINS_PATH,
            schedules_source=SCHEDULES_PATH,
            calendar_provider=calendar_provider,
        )

        # 1. Stations Reconciliation
        assert len(dataset.stations) == 8697
        assert len(dataset.quarantined_stations) == 293
        assert len(dataset.stations) + len(dataset.quarantined_stations) == 8990

        # 2. Trains Reconciliation
        assert len(dataset.train_records) == 5175
        assert len(dataset.quarantined_trains) == 33
        assert len(dataset.train_records) + len(dataset.quarantined_trains) == 5208

        # 3. Schedules Reconciliation
        assert len(dataset.train_schedules) == 5175
        assert len(dataset.schedule_stops) == 414176
        assert len(dataset.quarantined_schedule_stops) == 2904
        assert len(dataset.schedule_stops) + len(dataset.quarantined_schedule_stops) == 417080

        # Incomplete Timing preservation
        incomplete_stops = [s for s in dataset.schedule_stops if not s.is_timing_complete]
        complete_stops = [s for s in dataset.schedule_stops if s.is_timing_complete]
        assert len(complete_stops) == 392420
        assert len(incomplete_stops) == 21756

        # Missing Day Preservation (Zero-Fabrication in Accepted Stops)
        missing_days = [s for s in dataset.schedule_stops if s.day is None]
        assert len(missing_days) == 21629
        for s in missing_days:
            assert s.day_offset is None, "Missing day must strictly produce None day_offset"

        # 4. Tier 2 Compiled Domain Trains
        # From the 12 bootstrap trains, 8 exist in DataMeet with matching endpoints and clean schedules
        assert len(dataset.compiled_trains) == 8
        compiled_numbers = {t.number for t in dataset.compiled_trains}
        expected_compiled = {"12951", "12952", "12002", "12001", "12301", "12302", "12953", "12954"}
        assert compiled_numbers == expected_compiled

        for ct in dataset.compiled_trains:
            assert isinstance(ct, Train)
            assert len(ct.schedule) > 0
            assert ct.origin_code == ct.schedule[0].station_code
            assert ct.destination_code == ct.schedule[-1].station_code
            assert len(ct.runs_on_days) > 0

        # 5. Non-compiling trains are transparently categorized
        assert len(dataset.uncompiled_trains) == 5175 - 8
        for ut in dataset.uncompiled_trains:
            assert ut.is_compilable_to_domain is False
            assert len(ut.uncompilable_reasons) > 0

        # Provenance verification
        assert dataset.station_provenance is not None
        assert dataset.train_provenance is not None
        assert dataset.schedule_provenance is not None
        assert dataset.station_provenance.file_size_bytes == 1864683
        assert dataset.train_provenance.file_size_bytes == 14768598
        assert dataset.schedule_provenance.file_size_bytes == 82174280
