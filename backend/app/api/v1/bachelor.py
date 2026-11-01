"""
Bachelor Special API: Discovery of multi-segment vacant berth itineraries
on the same train and journey date.
"""

from typing import List, Optional
import datetime
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal
from app.domain.services.bachelor_service import BachelorSpecialService

router = APIRouter(prefix="/bachelor", tags=["bachelor"])


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


class BerthSegmentSchema(BaseModel):
    segment_id: str
    train_number: str
    date: datetime.date
    coach: str
    berth_number: int
    berth_type: str
    from_station_code: str
    to_station_code: str
    from_sequence: int
    to_sequence: int


class BachelorSpecialItinerarySchema(BaseModel):
    train_number: str
    train_name: str
    origin_code: str
    destination_code: str
    travel_date: datetime.date
    travel_class: str
    segments: List[BerthSegmentSchema]
    total_segment_count: int
    berth_changes_count: int
    is_continuous: bool


class BachelorSpecialSearchResponse(BaseModel):
    origin_code: str
    destination_code: str
    travel_date: datetime.date
    travel_class: Optional[str] = None
    total_itineraries: int
    itineraries: List[BachelorSpecialItinerarySchema]
    status: str
    data_source: str
    is_live_source: bool
    chart_policy_notice: str


@router.get("/search", response_model=BachelorSpecialSearchResponse)
async def search_bachelor_special(
    origin: str = Query(..., min_length=2, max_length=10, description="Origin station code (e.g. GWL)"),
    destination: str = Query(..., min_length=2, max_length=10, description="Destination station code (e.g. BPL)"),
    date: datetime.date = Query(..., description="Date of travel (YYYY-MM-DD)"),
    travel_class: Optional[str] = Query(None, description="Optional travel class filter (e.g. 3A, 2A, SL)"),
    session: AsyncSession = Depends(get_db),
):
    """
    Search for Bachelor Special continuous berth itineraries on the same train.
    Combines multiple vacant berth segments without requiring train interchanges.
    """
    orig_clean = origin.strip().upper()
    dest_clean = destination.strip().upper()

    if orig_clean == dest_clean:
        raise HTTPException(
            status_code=400,
            detail="Origin and destination stations cannot be identical.",
        )

    service = BachelorSpecialService(session=session)
    result = await service.search_bachelor_special(
        origin_code=orig_clean,
        destination_code=dest_clean,
        travel_date=date,
        travel_class=travel_class,
    )

    formatted_itineraries = [
        BachelorSpecialItinerarySchema(
            train_number=itin.train_number,
            train_name=itin.train_name,
            origin_code=itin.origin_code,
            destination_code=itin.destination_code,
            travel_date=itin.travel_date,
            travel_class=itin.travel_class,
            segments=[
                BerthSegmentSchema(
                    segment_id=s.segment_id,
                    train_number=s.train_number,
                    date=s.date,
                    coach=s.coach,
                    berth_number=s.berth_number,
                    berth_type=s.berth_type,
                    from_station_code=s.from_station_code,
                    to_station_code=s.to_station_code,
                    from_sequence=s.from_sequence,
                    to_sequence=s.to_sequence,
                )
                for s in itin.segments
            ],
            total_segment_count=itin.total_segment_count,
            berth_changes_count=max(0, itin.total_segment_count - 1),
            is_continuous=itin.is_continuous,
        )
        for itin in result.itineraries
    ]

    return BachelorSpecialSearchResponse(
        origin_code=result.origin_code,
        destination_code=result.destination_code,
        travel_date=result.travel_date,
        travel_class=result.travel_class,
        total_itineraries=result.total_itineraries,
        itineraries=formatted_itineraries,
        status=result.status,
        data_source=result.data_source,
        is_live_source=result.is_live_source,
        chart_policy_notice=result.chart_policy_notice,
    )

