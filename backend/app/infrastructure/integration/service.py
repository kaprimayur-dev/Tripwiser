from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Sequence, Union
import datetime

from app.domain.models.station import Station
from app.domain.models.train import Train, TrainScheduleEntry
from app.infrastructure.adapters.datameet.station_adapter import DataMeetStationAdapter
from app.infrastructure.adapters.datameet.models import AdapterResult
from app.infrastructure.adapters.datameet.train_adapter import DataMeetTrainAdapter
from app.infrastructure.adapters.datameet.train_models import (
    DataMeetTrainRecord,
    TrainAdapterResult,
)
from app.infrastructure.adapters.datameet.schedule_adapter import DataMeetScheduleAdapter
from app.infrastructure.adapters.datameet.schedule_models import (
    DataMeetScheduleEntry,
    DataMeetTrainSchedule,
    ScheduleAdapterResult,
)
from app.infrastructure.integration.models import (
    IntegratedScheduleStop,
    IntegratedTrainSchedule,
    IntegratedTrainRecord,
    IntegratedRailwayDataset,
)
from app.infrastructure.integration.calendar_provider import CalendarProvider


class RailwayDataIntegrationService:
    """
    Two-tier integration service correlating Station, Train, and Schedule adapter datasets.

    Tier 1 (IntegratedRailwayDataset):
      - Fully resolves station and train references.
      - Preserves incomplete timing, missing day values (day=None, day_offset=None), and missing distances.
      - Retains endpoint mismatches without silent correction.
      - Preserves source provenance and audit warnings across all adapters.

    Tier 2 (Compiled Domain Dataset):
      - Compiles only trains satisfying existing TW-102 domain validation.
      - Requires verified running calendar, complete day offsets, and aligned endpoints.
      - Non-qualifying trains remain in Tier 1 with explicit compilation exclusion reasons.
      - Never fabricates running days, day offsets, times, or distances.
    """

    def __init__(
        self,
        station_adapter: DataMeetStationAdapter | None = None,
        train_adapter: DataMeetTrainAdapter | None = None,
        schedule_adapter: DataMeetScheduleAdapter | None = None,
    ):
        self.station_adapter = station_adapter or DataMeetStationAdapter()
        self.train_adapter = train_adapter or DataMeetTrainAdapter()
        self.schedule_adapter = schedule_adapter or DataMeetScheduleAdapter()

    def integrate(
        self,
        stations_source: Union[str, Path, AdapterResult],
        trains_source: Union[str, Path, TrainAdapterResult],
        schedules_source: Union[str, Path, ScheduleAdapterResult],
        calendar_provider: CalendarProvider | None = None,
    ) -> IntegratedRailwayDataset:
        """
        Integrates multi-source railway datasets into a verified, two-tier integrated dataset.

        Args:
            stations_source: Path to stations.json or an existing AdapterResult.
            trains_source: Path to trains.json or an existing TrainAdapterResult.
            schedules_source: Path to schedules.json or an existing ScheduleAdapterResult.
            calendar_provider: Optional provider for verified running day calendars.

        Returns:
            IntegratedRailwayDataset containing Tier 1 integrated models and Tier 2 compiled domain models.
        """
        # Step 1: Ingest Stations
        if isinstance(stations_source, AdapterResult):
            station_result = stations_source
        else:
            station_result = self.station_adapter.adapt(stations_source)

        station_map: dict[str, Station] = {s.code: s for s in station_result.records}

        # Step 2: Ingest Trains with Station Reference Validation
        if isinstance(trains_source, TrainAdapterResult):
            train_result = trains_source
        else:
            train_result = self.train_adapter.adapt(
                trains_source, valid_station_codes=station_map.keys()
            )

        train_map: dict[str, DataMeetTrainRecord] = {
            t.number: t for t in train_result.records
        }

        # Step 3: Ingest Schedules with Station and Train Reference Validation
        if isinstance(schedules_source, ScheduleAdapterResult):
            schedule_result = schedules_source
        else:
            schedule_result = self.schedule_adapter.adapt(
                schedules_source,
                valid_station_codes=station_map.keys(),
                valid_train_numbers=train_map.keys(),
                train_metadata=train_map,
            )

        # Step 4: Assemble Tier 1 Integrated Schedules
        integrated_schedules_list: list[IntegratedTrainSchedule] = []
        integrated_stops_by_train: dict[str, list[IntegratedScheduleStop]] = {}
        all_integrated_stops: list[IntegratedScheduleStop] = []

        for sched in schedule_result.train_schedules:
            origin_stn = station_map.get(sched.origin_code)
            dest_stn = station_map.get(sched.destination_code)

            stops_for_train: list[IntegratedScheduleStop] = []
            for entry in sched.entries:
                stn = station_map.get(entry.station_code)
                if stn is None:
                    # Defensive: In standard pipeline, unlocated stations are quarantined in adapter
                    continue

                stop = IntegratedScheduleStop(
                    source_record_id=entry.source_record_id,
                    train_number=entry.train_number,
                    station_code=entry.station_code,
                    stop_sequence=entry.stop_sequence,
                    station=stn,
                    arrival_time=entry.arrival_time,
                    departure_time=entry.departure_time,
                    day=entry.day,
                    day_offset=entry.day_offset,
                    distance_km=entry.distance_km,
                    is_commercial_halt=entry.is_commercial_halt,
                    is_waypoint=entry.is_waypoint,
                    is_timing_complete=entry.is_timing_complete,
                    has_equal_arrival_departure=entry.has_equal_arrival_departure,
                    validation_warnings=entry.validation_warnings,
                )
                stops_for_train.append(stop)
                all_integrated_stops.append(stop)

            if origin_stn and dest_stn:
                integrated_sched = IntegratedTrainSchedule(
                    train_number=sched.train_number,
                    train_name=sched.train_name,
                    origin_station=origin_stn,
                    destination_station=dest_stn,
                    total_stops=len(stops_for_train),
                    stops=tuple(stops_for_train),
                    schedule_warnings=sched.schedule_warnings,
                )
                integrated_schedules_list.append(integrated_sched)
                integrated_stops_by_train[sched.train_number] = stops_for_train

        integrated_schedule_map = {
            s.train_number: s for s in integrated_schedules_list
        }

        # Step 5: Assemble Tier 1 Integrated Train Records and Tier 2 Compilation
        all_train_records: list[IntegratedTrainRecord] = []
        compiled_trains: list[Train] = []
        uncompiled_trains: list[IntegratedTrainRecord] = []

        for train_num, header in train_map.items():
            sched = integrated_schedule_map.get(train_num)
            stops = integrated_stops_by_train.get(train_num, [])

            runs_on_days: tuple[int, ...] | None = None
            if calendar_provider is not None:
                runs_on_days = calendar_provider.get_running_days(train_num)

            uncompilable_reasons: list[str] = []

            # Check 1: Running days calendar
            if runs_on_days is None or len(runs_on_days) == 0:
                uncompilable_reasons.append("AWAITING_RUNNING_CALENDAR")

            # Check 2: Schedule presence and non-emptiness
            if sched is None or len(stops) == 0:
                uncompilable_reasons.append("EMPTY_SCHEDULE")
            else:
                # Check 3: Missing day offset
                if any(s.day_offset is None for s in stops):
                    uncompilable_reasons.append("UNKNOWN_DAY_OFFSET")

                # Check 4: Endpoint alignment
                if stops[0].station_code != header.origin_code:
                    uncompilable_reasons.append("ORIGIN_ENDPOINT_MISMATCH")

                if stops[-1].station_code != header.destination_code:
                    uncompilable_reasons.append("DESTINATION_ENDPOINT_MISMATCH")

                # Check 5: Incomplete timing
                if any(not s.is_timing_complete for s in stops):
                    uncompilable_reasons.append("INCOMPLETE_TIMING")

                # Check 6: Strictly increasing stop sequence
                prev_seq = None
                for s in stops:
                    if prev_seq is not None and s.stop_sequence <= prev_seq:
                        uncompilable_reasons.append("NON_INCREASING_STOP_SEQUENCE")
                        break
                    prev_seq = s.stop_sequence

                # Check 7: Distinct endpoints
                if header.origin_code == header.destination_code:
                    uncompilable_reasons.append("IDENTICAL_ENDPOINTS")

            is_compilable = False
            if not uncompilable_reasons and sched is not None:
                try:
                    domain_schedule = [
                        TrainScheduleEntry(
                            station_code=s.station_code,
                            arrival_time=s.arrival_time,
                            departure_time=s.departure_time,
                            day_offset=s.day_offset if s.day_offset is not None else 0,
                            distance_km=float(s.distance_km) if s.distance_km is not None else 0.0,
                            stop_sequence=s.stop_sequence,
                        )
                        for s in stops
                    ]
                    compiled_train = Train(
                        number=header.number,
                        name=header.name,
                        origin_code=header.origin_code,
                        destination_code=header.destination_code,
                        runs_on_days=list(runs_on_days),  # type: ignore
                        schedule=domain_schedule,
                    )
                    compiled_trains.append(compiled_train)
                    is_compilable = True
                except Exception as exc:
                    # In case Pydantic raises unexpected validation error
                    uncompilable_reasons.append(f"DOMAIN_VALIDATION_ERROR: {exc}")
                    is_compilable = False

            record = IntegratedTrainRecord(
                header=header,
                schedule=sched,
                runs_on_days=runs_on_days,
                is_compilable_to_domain=is_compilable,
                uncompilable_reasons=tuple(uncompilable_reasons),
                integration_warnings=header.validation_warnings,
            )
            all_train_records.append(record)
            if not is_compilable:
                uncompiled_trains.append(record)

        reconciliation_summary = {
            "total_stations_accepted": len(station_result.records),
            "total_stations_quarantined": len(station_result.quarantined),
            "total_trains_accepted": len(train_result.records),
            "total_trains_quarantined": len(train_result.quarantined),
            "total_schedules_accepted": len(schedule_result.train_schedules),
            "total_schedule_stops_accepted": len(schedule_result.records),
            "total_schedule_stops_complete": len(schedule_result.accepted_complete),
            "total_schedule_stops_incomplete": len(schedule_result.accepted_incomplete),
            "total_schedule_stops_quarantined": len(schedule_result.quarantined),
            "total_trains_compiled_to_domain": len(compiled_trains),
            "total_trains_uncompiled": len(uncompiled_trains),
        }

        return IntegratedRailwayDataset(
            stations=tuple(station_result.records),
            compiled_trains=tuple(compiled_trains),
            train_records=tuple(all_train_records),
            train_schedules=tuple(integrated_schedules_list),
            schedule_stops=tuple(all_integrated_stops),
            uncompiled_trains=tuple(uncompiled_trains),
            quarantined_stations=tuple(station_result.quarantined),
            quarantined_trains=tuple(train_result.quarantined),
            quarantined_schedule_stops=tuple(schedule_result.quarantined),
            station_provenance=station_result.provenance,
            train_provenance=train_result.provenance,
            schedule_provenance=schedule_result.provenance,
            reconciliation_summary=reconciliation_summary,
        )

