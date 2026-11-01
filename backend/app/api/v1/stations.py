"""
Station API endpoints for autocomplete, lookup, and spatial search.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, Path
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal
from app.infrastructure.database.repositories.station_repository import SQLAlchemyStationRepository

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


@router.get("/search", response_model=List[StationResponse])
async def search_stations(
    q: str = Query(..., min_length=1, description="Station code, name, or city search query"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of stations to return"),
    session: AsyncSession = Depends(get_db),
):
    """Searches stations by code, name, or city prefix/substring for search inputs."""
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
    latitude: float = Query(..., ge=-90.0, le=90.0, description="Target latitude"),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="Target longitude"),
    radius_km: float = Query(25.0, ge=1.0, le=200.0, description="Search radius in kilometers"),
    session: AsyncSession = Depends(get_db),
):
    """Finds stations within a geographic radius using PostGIS ST_DWithin queries."""
    repo = SQLAlchemyStationRepository(session)
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
        for s, dist in nearby
    ]


@router.get("/{code}", response_model=StationResponse)
async def get_station_by_code(
    code: str = Path(..., description="Station code (e.g. NDLS, BCT)"),
    session: AsyncSession = Depends(get_db),
):
    """Retrieves full details for a station by code."""
    repo = SQLAlchemyStationRepository(session)
    station = await repo.get_by_code(code.strip().upper())
    if not station:
        raise HTTPException(status_code=404, detail=f"Station '{code}' not found")
    return StationResponse(
        code=station.code,
        name=station.name,
        city=station.city,
        state=station.state,
        zone=station.zone,
        latitude=station.latitude,
        longitude=station.longitude,
    )

