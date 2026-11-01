"""
Station API endpoints for autocomplete, lookup, spatial search, and timetable coverage.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal
from app.infrastructure.database.repositories.station_repository import SQLAlchemyStationRepository
from app.api.v1.trains import get_trains_for_station_core, StationTrainsResponse

router = APIRouter(prefix="/stations", tags=["stations"])


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


class StationResponse(BaseModel):
    code: str
    name: str
    city: Optional[str] = None
    state: Optional[str] = None
    zone: Optional[str] = None
    latitude: float
    longitude: float


class NearbyStationResponse(BaseModel):
    station: StationResponse
    distance_km: float


class StationCoverageSchema(BaseModel):
    has_timetable_coverage: bool
    total_compiled_trains: int
    originating_trains_count: int
    terminating_trains_count: int
    coverage_status: str
    coverage_note: str


class StationDetailResponse(StationResponse):
    timetable_coverage: StationCoverageSchema


@router.get("/search", response_model=List[StationResponse])
async def search_stations(
    q: str = Query(..., min_length=1, max_length=50, description="Station code, name, or city search query"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of stations to return"),
    session: AsyncSession = Depends(get_db),
):
    """
    Searches stations by code, name, or city with exact station code matches prioritized.
    Supports partial and case-insensitive matching.
    """
    repo = SQLAlchemyStationRepository(session)
    stations = await repo.search_by_name_or_code(query=q, limit=limit)
    return [
        StationResponse(
            code=s.code,
            name=s.name,
            city=s.city,
            state=s.state,
            zone=s.zone,
            latitude=s.latitude,
            longitude=s.longitude,
        )
        for s in stations
    ]


@router.get("/nearby", response_model=List[NearbyStationResponse])
async def get_nearby_stations(
    station_code: Optional[str] = Query(None, min_length=1, max_length=10, description="Source station code to find neighbors around"),
    latitude: Optional[float] = Query(None, ge=-90.0, le=90.0, description="Target latitude (if station_code not supplied)"),
    longitude: Optional[float] = Query(None, ge=-180.0, le=180.0, description="Target longitude (if station_code not supplied)"),
    radius_km: float = Query(25.0, ge=1.0, le=200.0, description="Search radius in kilometers"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of nearby stations to return"),
    session: AsyncSession = Depends(get_db),
):
    """
    Finds stations within a geographic radius using PostGIS ST_DWithin queries.
    Supports querying by source station code (excluding the source station itself)
    or by explicit geographic coordinates.
    """
    repo = SQLAlchemyStationRepository(session)
    if station_code:
        clean_code = station_code.strip().upper()
        nearby = await repo.get_nearby_stations_by_code(clean_code, radius_km=radius_km, limit=limit)
        if nearby is None:
            raise HTTPException(status_code=404, detail=f"Station '{clean_code}' not found")
        return [
            NearbyStationResponse(
                station=StationResponse(
                    code=s.code,
                    name=s.name,
                    city=s.city,
                    state=s.state,
                    zone=s.zone,
                    latitude=s.latitude,
                    longitude=s.longitude,
                ),
                distance_km=round(dist, 2),
            )
            for s, dist in nearby
        ]
    elif latitude is not None and longitude is not None:
        nearby = await repo.get_nearby_stations(latitude=latitude, longitude=longitude, radius_km=radius_km)
        return [
            NearbyStationResponse(
                station=StationResponse(
                    code=s.code,
                    name=s.name,
                    city=s.city,
                    state=s.state,
                    zone=s.zone,
                    latitude=s.latitude,
                    longitude=s.longitude,
                ),
                distance_km=round(dist, 2),
            )
            for s, dist in nearby[:limit]
        ]
    else:
        raise HTTPException(
            status_code=400,
            detail="Must provide either 'station_code' or both 'latitude' and 'longitude'",
        )


@router.get("/{code}", response_model=StationDetailResponse)
async def get_station_by_code(
    code: str = Path(..., min_length=1, max_length=30, description="Station code (e.g. NDLS, BCT)"),
    session: AsyncSession = Depends(get_db),
):
    """
    Retrieves full details for a station by code, including geographic coordinates,
    location metadata, and honest timetable coverage statistics.
    """
    clean_code = code.strip().upper()
    repo = SQLAlchemyStationRepository(session)
    station = await repo.get_by_code(clean_code)
    if not station:
        raise HTTPException(status_code=404, detail=f"Station '{clean_code}' not found")

    coverage = await repo.get_station_coverage(clean_code)

    return StationDetailResponse(
        code=station.code,
        name=station.name,
        city=station.city,
        state=station.state,
        zone=station.zone,
        latitude=station.latitude,
        longitude=station.longitude,
        timetable_coverage=StationCoverageSchema(**coverage),
    )


@router.get("/{code}/trains", response_model=StationTrainsResponse)
async def get_station_trains(
    code: str = Path(..., min_length=1, max_length=30, description="Station code (e.g. NDLS, BCT)"),
    limit: int = Query(100, ge=1, le=200, description="Maximum number of trains to return"),
    session: AsyncSession = Depends(get_db),
):
    """
    Discovers all compiled timetable trains that serve this station (calling, originating, or terminating).
    """
    return await get_trains_for_station_core(station_code=code, limit=limit, session=session)
