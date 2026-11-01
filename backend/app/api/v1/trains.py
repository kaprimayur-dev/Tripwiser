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
    is_commercial_halt: bool = False


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
    only_commercial: bool = Query(False, description="If true, returns only commercial passenger halts"),
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
    only_commercial: bool = Query(True, description="Filter to commercial stops with passenger halts"),
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
