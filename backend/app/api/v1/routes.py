"""
Route Discovery API endpoints for journey search and alternatives.
"""

from typing import List, Optional
import datetime
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal
from app.domain.services.route_engine import RouteDiscoveryEngine
from app.api.v1.stations import StationResponse
from app.api.v1.trains import format_running_days

router = APIRouter(prefix="/routes", tags=["routes"])


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


class AvailabilitySchema(BaseModel):
    status: str
    available_count: Optional[int] = None
    waitlist_count: Optional[int] = None
    quota: Optional[str] = None
    travel_class: Optional[str] = None
    fare: Optional[float] = None
    source: Optional[str] = None


class LegSchema(BaseModel):
    train_number: str
    train_name: str
    origin_code: str
    destination_code: str
    departure_time: datetime.datetime
    arrival_time: datetime.datetime
    duration_minutes: int
    travel_class: Optional[str] = None
    distance_km: float
    timetable_status: str = "TIMETABLE_CONFIRMED"
    availability: Optional[AvailabilitySchema] = None
    runs_on_days: Optional[List[int]] = None
    frequency_description: Optional[str] = None
    intermediate_stop_count: int = 0


class LayoverSchema(BaseModel):
    interchange_station_code: str
    arriving_train_number: str
    departing_train_number: str
    arrival_time: datetime.datetime
    departure_time: datetime.datetime
    duration_minutes: int
    risk_level: str
    risk_label: str
    risk_description: str


class RouteSchema(BaseModel):
    route_id: str
    is_direct: bool
    transfer_count: int
    total_duration_minutes: int
    total_fare: Optional[float] = None
    transfer_durations_minutes: List[int]
    score: float
    legs: List[LegSchema]
    # TW-113 Journey Breakdown & Risk Intelligence
    total_travel_time_minutes: int = 0
    total_wait_time_minutes: int = 0
    layovers: List[LayoverSchema] = Field(default_factory=list)
    insights: List[str] = Field(default_factory=list)
    overall_transfer_risk: Optional[str] = None


class RouteSearchQuerySchema(BaseModel):
    origin: str
    destination: str
    journey_date: datetime.date
    max_transfers: int
    sort_by: str


class RouteSearchResponse(BaseModel):
    query: RouteSearchQuerySchema
    origin_station: Optional[StationResponse] = None
    destination_station: Optional[StationResponse] = None
    total_routes_found: int
    direct_routes_count: int
    transfer_routes_count: int
    timetable_status: str = "TIMETABLE_CONFIRMED"
    fare_status: str
    availability_status: str
    sorting_applied: str
    sorting_note: Optional[str] = None
    no_route_reason: Optional[str] = None
    routes: List[RouteSchema]


@router.get("/search", response_model=RouteSearchResponse)
async def search_routes(
    origin: str = Query(..., min_length=1, description="Origin station code (e.g. BCT, NDLS, GWL)"),
    destination: str = Query(..., min_length=1, description="Destination station code (e.g. NDLS, BPL, HWH)"),
    date: str = Query(..., description="Journey date in YYYY-MM-DD format"),
    max_transfers: int = Query(1, ge=0, le=2, description="Maximum transfers allowed (0=direct only, 1=one transfer)"),
    sort_by: str = Query("recommended", pattern="^(recommended|fastest|fewest_transfers|cheapest)$"),
    session: AsyncSession = Depends(get_db),
):
    """
    Searches direct and connecting railway routes between origin and destination on a given date.
    Respects train operating days and day offsets, enforcing realistic transfer buffer times.
    """
    try:
        journey_date = datetime.date.fromisoformat(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Expected YYYY-MM-DD.")

    if origin.strip().upper() == destination.strip().upper():
        raise HTTPException(
            status_code=400,
            detail="Origin and destination stations cannot be identical.",
        )

    engine = RouteDiscoveryEngine(session)
    result = await engine.search_routes(
        origin_code=origin,
        destination_code=destination,
        journey_date=journey_date,
        max_transfers=max_transfers,
        sort_by=sort_by,
    )

    if result.no_route_reason == "STATION_NOT_FOUND":
        raise HTTPException(
            status_code=404,
            detail=f"One or both stations ('{origin}', '{destination}') could not be found in the station master.",
        )

    routes_data = [
        RouteSchema(
            route_id=r.route_id,
            is_direct=r.is_direct,
            transfer_count=r.transfer_count,
            total_duration_minutes=r.total_duration_minutes,
            total_fare=r.total_fare,
            transfer_durations_minutes=r.transfer_durations_minutes,
            score=r.score,
            total_travel_time_minutes=r.total_travel_time_minutes,
            total_wait_time_minutes=r.total_wait_time_minutes,
            layovers=[
                LayoverSchema(
                    interchange_station_code=lay.interchange_station_code,
                    arriving_train_number=lay.arriving_train_number,
                    departing_train_number=lay.departing_train_number,
                    arrival_time=lay.arrival_time,
                    departure_time=lay.departure_time,
                    duration_minutes=lay.duration_minutes,
                    risk_level=lay.risk_level.value if hasattr(lay.risk_level, 'value') else str(lay.risk_level),
                    risk_label=lay.risk_label,
                    risk_description=lay.risk_description,
                )
                for lay in r.layovers
            ],
            insights=r.insights,
            overall_transfer_risk=r.overall_transfer_risk,
            legs=[
                LegSchema(
                    train_number=leg.train_number,
                    train_name=leg.train_name,
                    origin_code=leg.origin_code,
                    destination_code=leg.destination_code,
                    departure_time=leg.departure_time,
                    arrival_time=leg.arrival_time,
                    duration_minutes=leg.duration_minutes,
                    travel_class=leg.travel_class,
                    distance_km=leg.distance_km,
                    timetable_status="TIMETABLE_CONFIRMED",
                    runs_on_days=leg.runs_on_days,
                    frequency_description=format_running_days(leg.runs_on_days) if leg.runs_on_days else None,
                    intermediate_stop_count=leg.intermediate_stop_count,
                    availability=(
                        AvailabilitySchema(
                            status=leg.availability.status.value,
                            available_count=leg.availability.available_count,
                            waitlist_count=leg.availability.waitlist_count,
                            quota=leg.availability.quota,
                            travel_class=leg.availability.travel_class,
                            fare=leg.availability.fare,
                            source=leg.availability.source,
                        )
                        if leg.availability is not None
                        else None
                    ),
                )
                for leg in r.legs
            ],
        )
        for r in result.routes
    ]

    orig_st = (
        StationResponse(
            code=result.origin_station.code,
            name=result.origin_station.name,
            city=result.origin_station.city,
            state=result.origin_station.state,
            zone=result.origin_station.zone,
            latitude=result.origin_station.latitude,
            longitude=result.origin_station.longitude,
        )
        if result.origin_station
        else None
    )

    dest_st = (
        StationResponse(
            code=result.destination_station.code,
            name=result.destination_station.name,
            city=result.destination_station.city,
            state=result.destination_station.state,
            zone=result.destination_station.zone,
            latitude=result.destination_station.latitude,
            longitude=result.destination_station.longitude,
        )
        if result.destination_station
        else None
    )

    return RouteSearchResponse(
        query=RouteSearchQuerySchema(
            origin=result.query.origin_code,
            destination=result.query.destination_code,
            journey_date=result.query.journey_date,
            max_transfers=result.query.max_transfers,
            sort_by=result.query.sort_by,
        ),
        origin_station=orig_st,
        destination_station=dest_st,
        total_routes_found=result.total_routes_found,
        direct_routes_count=result.direct_routes_count,
        transfer_routes_count=result.transfer_routes_count,
        timetable_status=result.timetable_status,
        fare_status=result.fare_status,
        availability_status=result.availability_status,
        sorting_applied=result.sorting_applied,
        sorting_note=result.sorting_note,
        no_route_reason=result.no_route_reason,
        routes=routes_data,
    )


# ---------------------------------------------------------------------------
# Network Intelligence & Interchange Endpoints (TW-112)
# ---------------------------------------------------------------------------

class TrainConnectivityItem(BaseModel):
    train_number: str
    train_name: str
    origin_code: str
    destination_code: str
    departure_time: str
    arrival_time: str
    day_difference: int
    duration_minutes: int
    distance_km: float
    runs_on_days: List[int]
    frequency_description: Optional[str] = None
    intermediate_stop_count: int
    origin_stop_sequence: int
    destination_stop_sequence: int


class StationConnectivityResponse(BaseModel):
    origin_code: str
    destination_code: str
    total_trains_count: int
    fastest_duration_minutes: Optional[int] = None
    average_duration_minutes: Optional[int] = None
    trains: List[TrainConnectivityItem]


class InterchangeStationItem(BaseModel):
    station_code: str
    station_name: str
    city: Optional[str] = None
    state: Optional[str] = None
    zone: Optional[str] = None
    latitude: float
    longitude: float
    inbound_trains_count: int
    outbound_trains_count: int
    connection_score: int
    sample_inbound_trains: List[str]
    sample_outbound_trains: List[str]


class InterchangeDiscoveryResponse(BaseModel):
    origin_code: Optional[str] = None
    destination_code: Optional[str] = None
    total_interchanges_found: int
    interchanges: List[InterchangeStationItem]


@router.get("/connectivity", response_model=StationConnectivityResponse)
async def get_station_connectivity(
    origin_code: str = Query(..., min_length=1, max_length=10, description="Origin station code (e.g. NDLS, BCT)"),
    destination_code: str = Query(..., min_length=1, max_length=10, description="Destination station code (e.g. BPL, HWH)"),
    session: AsyncSession = Depends(get_db),
):
    """
    Returns all compiled direct trains connecting two stations with scheduled timings,
    operating days, durations, intermediate halts, and distances.
    """
    orig_clean = origin_code.strip().upper()
    dest_clean = destination_code.strip().upper()

    if orig_clean == dest_clean:
        raise HTTPException(status_code=400, detail="Origin and destination stations cannot be identical.")

    engine = RouteDiscoveryEngine(session)
    orig_st = await engine.station_repo.get_by_code(orig_clean)
    dest_st = await engine.station_repo.get_by_code(dest_clean)
    if not orig_st or not dest_st:
        raise HTTPException(
            status_code=404,
            detail=f"One or both stations ('{orig_clean}', '{dest_clean}') not found in station database.",
        )

    res = await engine.get_station_connectivity(orig_clean, dest_clean)
    return StationConnectivityResponse(
        origin_code=res.origin_code,
        destination_code=res.destination_code,
        total_trains_count=res.total_trains_count,
        fastest_duration_minutes=res.fastest_duration_minutes,
        average_duration_minutes=res.average_duration_minutes,
        trains=[
            TrainConnectivityItem(
                train_number=tc.train_number,
                train_name=tc.train_name,
                origin_code=tc.origin_code,
                destination_code=tc.destination_code,
                departure_time=tc.departure_time.strftime("%H:%M"),
                arrival_time=tc.arrival_time.strftime("%H:%M"),
                day_difference=tc.day_difference,
                duration_minutes=tc.duration_minutes,
                distance_km=tc.distance_km,
                runs_on_days=tc.runs_on_days,
                frequency_description=format_running_days(tc.runs_on_days) if tc.runs_on_days else None,
                intermediate_stop_count=tc.intermediate_stop_count,
                origin_stop_sequence=tc.origin_stop_sequence,
                destination_stop_sequence=tc.destination_stop_sequence,
            )
            for tc in res.trains
        ],
    )


@router.get("/interchanges", response_model=InterchangeDiscoveryResponse)
async def get_interchanges(
    origin_code: Optional[str] = Query(None, min_length=1, max_length=10, description="Optional corridor origin code"),
    destination_code: Optional[str] = Query(None, min_length=1, max_length=10, description="Optional corridor destination code"),
    limit: int = Query(20, ge=1, le=50, description="Maximum interchange hubs to return"),
    session: AsyncSession = Depends(get_db),
):
    """
    Discovers interchange junction stations. When origin and destination are given,
    identifies transfer hubs linking inbound and outbound train services.
    When omitted, returns the highest-frequency junction hubs across Indian Railways.
    """
    orig_clean = origin_code.strip().upper() if origin_code else None
    dest_clean = destination_code.strip().upper() if destination_code else None

    if (orig_clean and not dest_clean) or (dest_clean and not orig_clean):
        raise HTTPException(
            status_code=400,
            detail="Must provide both 'origin_code' and 'destination_code' for corridor interchanges, or neither for global hubs.",
        )

    if orig_clean and dest_clean and orig_clean == dest_clean:
        raise HTTPException(status_code=400, detail="Origin and destination stations cannot be identical.")

    engine = RouteDiscoveryEngine(session)
    if orig_clean and dest_clean:
        orig_st = await engine.station_repo.get_by_code(orig_clean)
        dest_st = await engine.station_repo.get_by_code(dest_clean)
        if not orig_st or not dest_st:
            raise HTTPException(
                status_code=404,
                detail=f"One or both stations ('{orig_clean}', '{dest_clean}') not found in station database.",
            )

    interchanges = await engine.get_interchanges(orig_clean, dest_clean, limit=limit)
    return InterchangeDiscoveryResponse(
        origin_code=orig_clean,
        destination_code=dest_clean,
        total_interchanges_found=len(interchanges),
        interchanges=[
            InterchangeStationItem(
                station_code=ic.station_code,
                station_name=ic.station_name,
                city=ic.city,
                state=ic.state,
                zone=ic.zone,
                latitude=ic.latitude,
                longitude=ic.longitude,
                inbound_trains_count=ic.inbound_trains_count,
                outbound_trains_count=ic.outbound_trains_count,
                connection_score=ic.connection_score,
                sample_inbound_trains=ic.sample_inbound_trains,
                sample_outbound_trains=ic.sample_outbound_trains,
            )
            for ic in interchanges
        ],
    )


