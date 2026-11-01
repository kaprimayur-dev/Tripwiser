"""
Train Schedule and Stoppage Intelligence API endpoints.
Provides search, full timetable schedules, intermediate stoppage slicing, and verified running calendars.
"""

from typing import List, Optional, Dict, Any, Tuple
import datetime
from pathlib import Path
import json

from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal
from app.infrastructure.database.models.train import TrainORM, ScheduleORM
from app.infrastructure.database.repositories.train_repository import SQLAlchemyTrainRepository
from app.infrastructure.integration.calendar_provider import JsonCalendarProvider

router = APIRouter(prefix="/trains", tags=["trains"])


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def format_running_days(runs_on_days: List[int]) -> str:
    valid_days = sorted(set(d for d in runs_on_days if 0 <= d <= 6))
    if not valid_days:
        return "Not Scheduled"
    if len(valid_days) == 7:
        return "Daily (Mon-Sun)"
    if valid_days == [0, 1, 2, 3, 4, 5]:
        return "Except Sunday (Mon-Sat)"
    if valid_days == [0, 1, 2, 3, 5, 6]:
        return "Except Friday (Sat-Thu)"
    if valid_days == [0, 1, 2, 3, 4]:
        return "Weekdays (Mon-Fri)"
    return ", ".join(DAY_NAMES[d] for d in valid_days)


def calculate_halt_minutes(
    arrival: Optional[datetime.time],
    departure: Optional[datetime.time],
    arr_day_offset: int = 0,
    dep_day_offset: int = 0,
) -> int:
    if arrival is None or departure is None:
        return 0
    arr_m = arrival.hour * 60 + arrival.minute
    dep_m = departure.hour * 60 + departure.minute + (dep_day_offset - arr_day_offset) * 1440
    if dep_m < arr_m:
        dep_m += 1440
    return max(0, dep_m - arr_m)


# Lazy-loaded singleton providers
_calendar_provider: Optional[JsonCalendarProvider] = None
_quarantined_trains: Optional[Dict[str, Dict[str, Any]]] = None


def get_calendar_provider() -> JsonCalendarProvider:
    global _calendar_provider
    if _calendar_provider is None:
        candidates = [
            Path("backend/app/infrastructure/data/sources/official/railway_running_calendars.json"),
            Path("app/infrastructure/data/sources/official/railway_running_calendars.json"),
            Path("/app/app/infrastructure/data/sources/official/railway_running_calendars.json"),
        ]
        for p in candidates:
            if p.exists() and p.is_file():
                _calendar_provider = JsonCalendarProvider(p)
                break
        if _calendar_provider is None:
            _calendar_provider = JsonCalendarProvider(Path("railway_running_calendars.json"))
    return _calendar_provider


def get_quarantined_trains() -> Dict[str, Dict[str, Any]]:
    global _quarantined_trains
    if _quarantined_trains is None:
        _quarantined_trains = {}
        candidates = [
            Path("backend/data/quarantine/uncompiled_trains.json"),
            Path("data/quarantine/uncompiled_trains.json"),
            Path("/app/data/quarantine/uncompiled_trains.json"),
        ]
        for p in candidates:
            if p.exists() and p.is_file():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        _quarantined_trains = {
                            str(item.get("train_number")).strip(): item
                            for item in data
                            if isinstance(item, dict)
                        }
                    break
                except Exception:
                    pass
    return _quarantined_trains


# --- Schemas ---

class ScheduleStopSchema(BaseModel):
    stop_sequence: int
    station_code: str
    station_name: str
    arrival_time: Optional[str] = None
    departure_time: Optional[str] = None
    day_offset: int = 0
    distance_km: float = 0.0
    halt_minutes: int = 0
    is_commercial_halt: bool = Field(
        False,
        description="True if stop has positive scheduled dwell time (halt > 0) or is an endpoint. Reflects timetable dwell records only; does not certify passenger commercial booking permissions.",
    )


class TrainSummarySchema(BaseModel):
    number: str
    name: str
    origin_code: str
    origin_name: str
    destination_code: str
    destination_name: str
    runs_on_days: List[int]
    frequency_description: str
    total_stops: int
    distance_km: float
    provenance_tier: str


class TrainDetailSchema(BaseModel):
    number: str
    name: str
    origin_code: str
    origin_name: str
    destination_code: str
    destination_name: str
    runs_on_days: List[int]
    frequency_description: str
    total_stops: int
    distance_km: float
    source_document: Optional[str] = None
    publication_version: Optional[str] = None
    table_reference: Optional[str] = None
    provenance_tier: str


class TrainScheduleResponse(BaseModel):
    train: TrainDetailSchema
    total_stops: int
    commercial_stops_count: int
    stops: List[ScheduleStopSchema]


class IntermediateStopsResponse(BaseModel):
    train_number: str
    train_name: str
    from_station_code: str
    from_station_name: str
    to_station_code: str
    to_station_name: str
    intermediate_stop_count: int
    stops: List[ScheduleStopSchema]


class TrainComparisonItem(BaseModel):
    number: str
    name: str
    origin_code: str
    origin_name: str
    destination_code: str
    destination_name: str
    departure_time: Optional[str] = None
    arrival_time: Optional[str] = None
    day_offset_difference: int = 0
    scheduled_duration_minutes: Optional[int] = None
    duration_formatted: str = "--"
    distance_km: float = 0.0
    intermediate_stops_count: int = 0
    runs_on_days: List[int]
    frequency_description: str
    source_document: Optional[str] = None
    publication_version: Optional[str] = None
    table_reference: Optional[str] = None
    provenance_tier: str


class TrainComparisonResponse(BaseModel):
    origin_code: str
    origin_name: str
    destination_code: str
    destination_name: str
    total_trains: int
    trains: List[TrainComparisonItem]
    disclaimer: str = (
        "Static scheduled timetable comparison only. Seat availability, fares, and real-time train operations are strictly deferred."
    )


class StationTrainServiceSchema(BaseModel):
    train_number: str
    train_name: str
    origin_code: str
    origin_name: str
    destination_code: str
    destination_name: str
    arrival_time: Optional[str] = None
    departure_time: Optional[str] = None
    halt_minutes: int = 0
    day_offset: int = 0
    stop_sequence: int
    total_stops: int
    service_type: str  # "ORIGINATING", "TERMINATING", or "EN_ROUTE"
    runs_on_days: List[int]
    frequency_description: str
    table_reference: Optional[str] = None
    provenance_tier: str


class StationTrainsResponse(BaseModel):
    station_code: str
    station_name: str
    total_trains: int
    originating_count: int
    terminating_count: int
    calling_count: int
    trains: List[StationTrainServiceSchema]
    disclaimer: str = "Static timetable records only. Does not imply train is currently running."


# --- Helpers ---

def _build_train_detail(
    train: TrainORM,
    station_names: Dict[str, str],
    total_stops: int,
    distance_km: float,
) -> TrainDetailSchema:
    clean_num = train.number.strip()
    cal_prov = get_calendar_provider()
    prov = cal_prov.get_provenance(clean_num)

    freq_desc = (
        prov.get("operating_days_description")
        if prov and prov.get("operating_days_description")
        else format_running_days(train.runs_on_days)
    )

    return TrainDetailSchema(
        number=train.number,
        name=train.name,
        origin_code=train.origin_code,
        origin_name=station_names.get(train.origin_code, train.origin_code),
        destination_code=train.destination_code,
        destination_name=station_names.get(train.destination_code, train.destination_code),
        runs_on_days=list(train.runs_on_days),
        frequency_description=freq_desc,
        total_stops=total_stops,
        distance_km=distance_km,
        source_document=prov.get("source_document") if prov else None,
        publication_version=prov.get("publication_version") if prov else None,
        table_reference=prov.get("table_reference") if prov else None,
        provenance_tier=prov.get("provenance_tier", "OFFICIALLY_VERIFIED_INDIVIDUAL_TABLE_RECORD")
        if prov
        else "VERIFIED_TIMETABLE_RECORD",
    )


def _check_quarantine_or_404(clean_num: str):
    quarantined = get_quarantined_trains()
    if clean_num in quarantined:
        q_entry = quarantined[clean_num]
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "AWAITING_VERIFIED_SCHEDULE",
                "message": f"Train {clean_num} exists in railway network but schedule is not compiled or verified (quarantined)",
                "train_number": clean_num,
                "train_name": q_entry.get("train_name"),
                "exclusion_reasons": q_entry.get("exclusion_reasons", []),
            },
        )
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error_code": "TRAIN_NOT_FOUND",
            "message": f"Train {clean_num} not found in railway database",
            "train_number": clean_num,
        },
    )


# --- Endpoints ---

# Mandatory Requirement 9: Register static routes like /search before dynamic /{train_number}
@router.get("/search", response_model=List[TrainSummarySchema])
async def search_trains(
    q: str = Query(..., min_length=2, max_length=50, description="Train number or name substring"),
    limit: int = Query(10, ge=1, le=25, description="Maximum number of results to return"),
    session: AsyncSession = Depends(get_db),
):
    """
    Searches for trains matching the query by train number prefix or train name substring.
    """
    repo = SQLAlchemyTrainRepository(session)
    trains = await repo.search_trains(q, limit=limit)
    if not trains:
        return []

    # Batch fetch endpoint station names
    endpoint_codes = set()
    for t in trains:
        endpoint_codes.add(t.origin_code)
        endpoint_codes.add(t.destination_code)
    station_names = await repo.get_station_names_for_codes(list(endpoint_codes))

    cal_prov = get_calendar_provider()
    summaries: List[TrainSummarySchema] = []

    for t in trains:
        clean_num = t.number.strip()
        prov = cal_prov.get_provenance(clean_num)
        freq_desc = (
            prov.get("operating_days_description")
            if prov and prov.get("operating_days_description")
            else format_running_days(t.runs_on_days)
        )

        schedules = sorted(t.schedules, key=lambda x: x.stop_sequence)
        total_stops = len(schedules)
        distance_km = float(schedules[-1].distance_km) if schedules else 0.0

        summaries.append(
            TrainSummarySchema(
                number=t.number,
                name=t.name,
                origin_code=t.origin_code,
                origin_name=station_names.get(t.origin_code, t.origin_code),
                destination_code=t.destination_code,
                destination_name=station_names.get(t.destination_code, t.destination_code),
                runs_on_days=list(t.runs_on_days),
                frequency_description=freq_desc,
                total_stops=total_stops,
                distance_km=distance_km,
                provenance_tier=prov.get("provenance_tier", "OFFICIALLY_VERIFIED_INDIVIDUAL_TABLE_RECORD")
                if prov
                else "VERIFIED_TIMETABLE_RECORD",
            )
        )

    return summaries


def _format_minutes(mins: Optional[int]) -> str:
    if mins is None or mins < 0:
        return "--"
    h = mins // 60
    m = mins % 60
    if h == 0:
        return f"{m}m"
    if m == 0:
        return f"{h}h"
    return f"{h}h {m}m"


@router.get("/compare", response_model=TrainComparisonResponse)
async def compare_trains(
    origin: str = Query(..., min_length=1, max_length=10, description="Origin station code (e.g. NDLS)"),
    destination: str = Query(..., min_length=1, max_length=10, description="Destination station code (e.g. BPL)"),
    session: AsyncSession = Depends(get_db),
):
    """
    Compares all direct train services connecting origin and destination stations.
    Calculates exact scheduled travel durations, intermediate stop counts, and operating days.
    """
    orig_clean = origin.strip().upper()
    dest_clean = destination.strip().upper()

    if orig_clean == dest_clean:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Origin and destination stations cannot be identical ('{orig_clean}')",
        )

    repo = SQLAlchemyTrainRepository(session)
    stn_names = await repo.get_station_names_for_codes([orig_clean, dest_clean])
    if orig_clean not in stn_names:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Origin station '{orig_clean}' not found in station master",
        )
    if dest_clean not in stn_names:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Destination station '{dest_clean}' not found in station master",
        )

    direct_pairs = await repo.compare_direct_trains(orig_clean, dest_clean)
    cal_prov = get_calendar_provider()

    endpoint_codes = set([orig_clean, dest_clean])
    for t, _, _ in direct_pairs:
        endpoint_codes.add(t.origin_code)
        endpoint_codes.add(t.destination_code)
    all_stn_names = await repo.get_station_names_for_codes(list(endpoint_codes))

    items: List[TrainComparisonItem] = []
    for t, orig_s, dest_s in direct_pairs:
        clean_num = t.number.strip()
        prov = cal_prov.get_provenance(clean_num)
        freq_desc = (
            prov.get("operating_days_description")
            if prov and prov.get("operating_days_description")
            else format_running_days(t.runs_on_days)
        )

        dep_str = orig_s.departure_time.strftime("%H:%M:%S") if orig_s.departure_time else None
        arr_str = dest_s.arrival_time.strftime("%H:%M:%S") if dest_s.arrival_time else None

        day_diff = dest_s.day_offset - orig_s.day_offset
        dur_mins: Optional[int] = None
        if orig_s.departure_time and dest_s.arrival_time:
            dep_m = orig_s.departure_time.hour * 60 + orig_s.departure_time.minute
            arr_m = dest_s.arrival_time.hour * 60 + dest_s.arrival_time.minute + day_diff * 1440
            if arr_m < dep_m and day_diff == 0:
                arr_m += 1440
            dur_mins = max(0, arr_m - dep_m)

        dist_km = max(0.0, float(dest_s.distance_km - orig_s.distance_km))
        inter_count = max(0, dest_s.stop_sequence - orig_s.stop_sequence - 1)

        items.append(
            TrainComparisonItem(
                number=t.number,
                name=t.name,
                origin_code=t.origin_code,
                origin_name=all_stn_names.get(t.origin_code, t.origin_code),
                destination_code=t.destination_code,
                destination_name=all_stn_names.get(t.destination_code, t.destination_code),
                departure_time=dep_str,
                arrival_time=arr_str,
                day_offset_difference=day_diff,
                scheduled_duration_minutes=dur_mins,
                duration_formatted=_format_minutes(dur_mins),
                distance_km=dist_km,
                intermediate_stops_count=inter_count,
                runs_on_days=list(t.runs_on_days),
                frequency_description=freq_desc,
                source_document=prov.get("source_document") if prov else None,
                publication_version=prov.get("publication_version") if prov else None,
                table_reference=prov.get("table_reference") if prov else None,
                provenance_tier=prov.get("provenance_tier", "OFFICIALLY_VERIFIED_INDIVIDUAL_TABLE_RECORD")
                if prov
                else "VERIFIED_TIMETABLE_RECORD",
            )
        )

    items.sort(
        key=lambda x: (
            x.scheduled_duration_minutes if x.scheduled_duration_minutes is not None else 999999,
            x.departure_time or "99:99:99",
        )
    )

    return TrainComparisonResponse(
        origin_code=orig_clean,
        origin_name=all_stn_names.get(orig_clean, orig_clean),
        destination_code=dest_clean,
        destination_name=all_stn_names.get(dest_clean, dest_clean),
        total_trains=len(items),
        trains=items,
    )


async def get_trains_for_station_core(
    station_code: str,
    limit: int = 100,
    session: AsyncSession = None,
) -> StationTrainsResponse:
    """
    Core implementation to retrieve all compiled timetable trains that call at, originate from,
    or terminate at station_code. Used canonically via /api/v1/stations/{code}/trains.
    """
    clean_code = station_code.strip().upper()
    repo = SQLAlchemyTrainRepository(session)
    stn_names = await repo.get_station_names_for_codes([clean_code])
    if clean_code not in stn_names:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Station '{clean_code}' not found in station master",
        )

    rows = await repo.get_trains_serving_station(clean_code, limit=limit)
    cal_prov = get_calendar_provider()

    endpoint_codes = set([clean_code])
    for t, _, _, _, _ in rows:
        endpoint_codes.add(t.origin_code)
        endpoint_codes.add(t.destination_code)
    all_stn_names = await repo.get_station_names_for_codes(list(endpoint_codes))

    items: List[StationTrainServiceSchema] = []
    orig_count = 0
    term_count = 0
    calling_count = 0

    for t, s, min_seq, max_seq, total_stops in rows:
        clean_num = t.number.strip()
        prov = cal_prov.get_provenance(clean_num)
        freq_desc = (
            prov.get("operating_days_description")
            if prov and prov.get("operating_days_description")
            else format_running_days(t.runs_on_days)
        )

        halt_m = calculate_halt_minutes(s.arrival_time, s.departure_time, s.day_offset, s.day_offset)

        if s.stop_sequence == min_seq:
            service_type = "ORIGINATING"
            orig_count += 1
        elif s.stop_sequence == max_seq:
            service_type = "TERMINATING"
            term_count += 1
        else:
            service_type = "EN_ROUTE"
            calling_count += 1

        items.append(
            StationTrainServiceSchema(
                train_number=t.number,
                train_name=t.name,
                origin_code=t.origin_code,
                origin_name=all_stn_names.get(t.origin_code, t.origin_code),
                destination_code=t.destination_code,
                destination_name=all_stn_names.get(t.destination_code, t.destination_code),
                arrival_time=s.arrival_time.strftime("%H:%M:%S") if s.arrival_time else None,
                departure_time=s.departure_time.strftime("%H:%M:%S") if s.departure_time else None,
                halt_minutes=halt_m,
                day_offset=s.day_offset,
                stop_sequence=s.stop_sequence,
                total_stops=total_stops,
                service_type=service_type,
                runs_on_days=list(t.runs_on_days),
                frequency_description=freq_desc,
                table_reference=prov.get("table_reference") if prov else None,
                provenance_tier=prov.get("provenance_tier", "OFFICIALLY_VERIFIED_INDIVIDUAL_TABLE_RECORD")
                if prov
                else "VERIFIED_TIMETABLE_RECORD",
            )
        )

    return StationTrainsResponse(
        station_code=clean_code,
        station_name=all_stn_names.get(clean_code, clean_code),
        total_trains=len(items),
        originating_count=orig_count,
        terminating_count=term_count,
        calling_count=calling_count,
        trains=items,
    )


@router.get("/{train_number}", response_model=TrainDetailSchema)
async def get_train(
    train_number: str,
    session: AsyncSession = Depends(get_db),
):
    """
    Retrieves full train metadata, running days, origin, destination, and source provenance.
    Distinguishes compiled trains from quarantined trains and non-existent trains.
    """
    clean_num = train_number.strip().upper()
    repo = SQLAlchemyTrainRepository(session)
    train = await repo.get_by_number(clean_num)

    if not train:
        _check_quarantine_or_404(clean_num)

    # Fetch station names
    station_names = await repo.get_station_names_for_codes([train.origin_code, train.destination_code])
    schedules = train.schedule
    total_stops = len(schedules)
    distance_km = schedules[-1].distance_km if schedules else 0.0

    cal_prov = get_calendar_provider()
    prov = cal_prov.get_provenance(clean_num)
    freq_desc = (
        prov.get("operating_days_description")
        if prov and prov.get("operating_days_description")
        else format_running_days(train.runs_on_days)
    )

    return TrainDetailSchema(
        number=train.number,
        name=train.name,
        origin_code=train.origin_code,
        origin_name=station_names.get(train.origin_code, train.origin_code),
        destination_code=train.destination_code,
        destination_name=station_names.get(train.destination_code, train.destination_code),
        runs_on_days=train.runs_on_days,
        frequency_description=freq_desc,
        total_stops=total_stops,
        distance_km=distance_km,
        source_document=prov.get("source_document") if prov else None,
        publication_version=prov.get("publication_version") if prov else None,
        table_reference=prov.get("table_reference") if prov else None,
        provenance_tier=prov.get("provenance_tier", "OFFICIALLY_VERIFIED_INDIVIDUAL_TABLE_RECORD")
        if prov
        else "VERIFIED_TIMETABLE_RECORD",
    )


@router.get("/{train_number}/schedule", response_model=TrainScheduleResponse)
async def get_train_schedule(
    train_number: str,
    only_commercial: bool = Query(
        False,
        description="If true, filters by positive scheduled dwell time (halt > 0 minutes) or route endpoints. Note: describes timetable dwell data only; does not certify commercial passenger booking permissions.",
    ),
    session: AsyncSession = Depends(get_db),
):
    """
    Retrieves the complete ordered stoppage timetable for a train with station names,
    arrival/departure timings, halt durations in minutes, and cumulative distances.
    """
    clean_num = train_number.strip().upper()
    repo = SQLAlchemyTrainRepository(session)
    train = await repo.get_by_number(clean_num)

    if not train:
        _check_quarantine_or_404(clean_num)

    schedule_rows = await repo.get_schedule_with_stations(clean_num)
    if not schedule_rows:
        _check_quarantine_or_404(clean_num)

    station_names = await repo.get_station_names_for_codes([train.origin_code, train.destination_code])
    total_stops = len(schedule_rows)
    distance_km = float(schedule_rows[-1][0].distance_km) if schedule_rows else 0.0

    cal_prov = get_calendar_provider()
    prov = cal_prov.get_provenance(clean_num)
    freq_desc = (
        prov.get("operating_days_description")
        if prov and prov.get("operating_days_description")
        else format_running_days(train.runs_on_days)
    )

    train_detail = TrainDetailSchema(
        number=train.number,
        name=train.name,
        origin_code=train.origin_code,
        origin_name=station_names.get(train.origin_code, train.origin_code),
        destination_code=train.destination_code,
        destination_name=station_names.get(train.destination_code, train.destination_code),
        runs_on_days=train.runs_on_days,
        frequency_description=freq_desc,
        total_stops=total_stops,
        distance_km=distance_km,
        source_document=prov.get("source_document") if prov else None,
        publication_version=prov.get("publication_version") if prov else None,
        table_reference=prov.get("table_reference") if prov else None,
        provenance_tier=prov.get("provenance_tier", "OFFICIALLY_VERIFIED_INDIVIDUAL_TABLE_RECORD")
        if prov
        else "VERIFIED_TIMETABLE_RECORD",
    )

    stops: List[ScheduleStopSchema] = []
    commercial_count = 0

    for idx, (s, st_name) in enumerate(schedule_rows):
        is_first = (idx == 0)
        is_last = (idx == total_stops - 1)
        halt_m = calculate_halt_minutes(s.arrival_time, s.departure_time, s.day_offset, s.day_offset)
        is_comm = is_first or is_last or (halt_m > 0)
        if is_comm:
            commercial_count += 1

        if only_commercial and not is_comm:
            continue

        stops.append(
            ScheduleStopSchema(
                stop_sequence=s.stop_sequence,
                station_code=s.station_code,
                station_name=st_name,
                arrival_time=s.arrival_time.strftime("%H:%M:%S") if s.arrival_time else None,
                departure_time=s.departure_time.strftime("%H:%M:%S") if s.departure_time else None,
                day_offset=s.day_offset,
                distance_km=float(s.distance_km),
                halt_minutes=halt_m,
                is_commercial_halt=is_comm,
            )
        )

    return TrainScheduleResponse(
        train=train_detail,
        total_stops=total_stops,
        commercial_stops_count=commercial_count,
        stops=stops,
    )


@router.get("/{train_number}/intermediate-stops", response_model=IntermediateStopsResponse)
async def get_intermediate_stops(
    train_number: str,
    from_code: str = Query(..., min_length=1, max_length=10, description="Boarding station code"),
    to_code: str = Query(..., min_length=1, max_length=10, description="Deboarding station code"),
    only_commercial: bool = Query(
        True,
        description="If true, filters intermediate stops to those with positive scheduled dwell time (halt > 0 minutes). Note: describes timetable dwell data only; does not certify commercial passenger booking permissions.",
    ),
    session: AsyncSession = Depends(get_db),
):
    """
    Extracts strictly the intermediate stations between from_code and to_code on train_number.
    Validates station presence on the route, asserts monotonic stop sequences, and calculates halt durations.
    """
    clean_num = train_number.strip().upper()
    from_clean = from_code.strip().upper()
    to_clean = to_code.strip().upper()

    if from_clean == to_clean:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"from_code and to_code cannot be identical ('{from_clean}')",
        )

    repo = SQLAlchemyTrainRepository(session)
    train = await repo.get_by_number(clean_num)
    if not train:
        _check_quarantine_or_404(clean_num)

    schedule_rows = await repo.get_schedule_with_stations(clean_num)
    if not schedule_rows:
        _check_quarantine_or_404(clean_num)

    # Locate from_stop and to_stop
    from_stop: Optional[ScheduleORM] = None
    from_name: str = from_clean
    to_stop: Optional[ScheduleORM] = None
    to_name: str = to_clean

    for s, st_name in schedule_rows:
        if s.station_code == from_clean:
            from_stop = s
            from_name = st_name
        if s.station_code == to_clean:
            to_stop = s
            to_name = st_name

    if from_stop is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Station '{from_clean}' is not a scheduled stop on train {clean_num}",
        )
    if to_stop is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Station '{to_clean}' is not a scheduled stop on train {clean_num}",
        )
    if from_stop.stop_sequence >= to_stop.stop_sequence:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Reversed station order: '{from_clean}' (seq {from_stop.stop_sequence}) occurs after '{to_clean}' (seq {to_stop.stop_sequence}) on train {clean_num}",
        )

    # Slice intermediate stations strictly between from_sequence and to_sequence
    intermediate_rows = [
        (s, name)
        for s, name in schedule_rows
        if from_stop.stop_sequence < s.stop_sequence < to_stop.stop_sequence
    ]

    stops: List[ScheduleStopSchema] = []
    for s, st_name in intermediate_rows:
        halt_m = calculate_halt_minutes(s.arrival_time, s.departure_time, s.day_offset, s.day_offset)
        is_comm = (halt_m > 0)
        if only_commercial and not is_comm:
            continue

        stops.append(
            ScheduleStopSchema(
                stop_sequence=s.stop_sequence,
                station_code=s.station_code,
                station_name=st_name,
                arrival_time=s.arrival_time.strftime("%H:%M:%S") if s.arrival_time else None,
                departure_time=s.departure_time.strftime("%H:%M:%S") if s.departure_time else None,
                day_offset=s.day_offset,
                distance_km=float(s.distance_km),
                halt_minutes=halt_m,
                is_commercial_halt=is_comm,
            )
        )

    return IntermediateStopsResponse(
        train_number=train.number,
        train_name=train.name,
        from_station_code=from_clean,
        from_station_name=from_name,
        to_station_code=to_clean,
        to_station_name=to_name,
        intermediate_stop_count=len(stops),
        stops=stops,
    )
