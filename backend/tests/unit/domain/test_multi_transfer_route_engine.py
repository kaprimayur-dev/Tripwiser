"""
Unit and integration tests for TW-112:
Multi-transfer route discovery, network intelligence, station connectivity, and interchange discovery.
"""

import pytest
import datetime
from sqlalchemy import text

from app.core.db import AsyncSessionLocal
from app.domain.services.route_engine import RouteDiscoveryEngine


@pytest.mark.asyncio
async def test_station_connectivity_direct_trains():
    """Verify station-to-station connectivity returns genuine compiled direct trains with timings and stops."""
    async with AsyncSessionLocal() as session:
        engine = RouteDiscoveryEngine(session)
        conn = await engine.get_station_connectivity("NDLS", "BPL")

        assert conn.origin_code == "NDLS"
        assert conn.destination_code == "BPL"
        assert conn.total_trains_count > 0
        assert conn.fastest_duration_minutes is not None
        assert conn.fastest_duration_minutes > 0

        # Train 12002 (Bhopal Shatabdi) connects NDLS -> BPL
        shatabdi = next((t for t in conn.trains if t.train_number == "12002"), None)
        assert shatabdi is not None
        assert shatabdi.train_name == "New Delhi-Bhopal Shatabdi Express"
        assert shatabdi.departure_time == datetime.time(6, 15)
        assert shatabdi.arrival_time == datetime.time(14, 5)
        assert shatabdi.day_difference == 0
        assert shatabdi.duration_minutes == 470
        assert shatabdi.distance_km >= 0
        assert 0 in shatabdi.runs_on_days  # Monday
        assert shatabdi.intermediate_stop_count > 0


@pytest.mark.asyncio
async def test_interchanges_corridor_discovery():
    """Verify corridor interchange discovery finds valid connecting hubs between services."""
    async with AsyncSessionLocal() as session:
        engine = RouteDiscoveryEngine(session)
        interchanges = await engine.get_interchanges("BCT", "HWH", limit=10)

        assert len(interchanges) > 0
        for ic in interchanges:
            assert ic.station_code not in ("BCT", "HWH")
            assert ic.inbound_trains_count > 0
            assert ic.outbound_trains_count > 0
            assert ic.connection_score >= 1
            assert len(ic.sample_inbound_trains) > 0
            assert len(ic.sample_outbound_trains) > 0
            assert ic.latitude != 0.0
            assert ic.longitude != 0.0


@pytest.mark.asyncio
async def test_global_interchanges_discovery():
    """Verify global network interchange discovery returns top railway junction hubs."""
    async with AsyncSessionLocal() as session:
        engine = RouteDiscoveryEngine(session)
        global_hubs = await engine.get_interchanges(limit=10)

        assert len(global_hubs) > 0
        hub_codes = [h.station_code for h in global_hubs]
        assert "NDLS" in hub_codes
        ndls_hub = next(h for h in global_hubs if h.station_code == "NDLS")
        assert ndls_hub.inbound_trains_count > 20
        assert ndls_hub.latitude > 20.0
        assert ndls_hub.longitude > 70.0


@pytest.mark.asyncio
async def test_two_transfer_route_search():
    """Verify multi-transfer route discovery safely finds 3-leg journeys without loops or buffer violations."""
    async with AsyncSessionLocal() as session:
        engine = RouteDiscoveryEngine(session)
        # Search corridor BCT -> HWH on 2026-11-02 (Monday) which connects via 2-transfer combinations
        journey_date = datetime.date(2026, 11, 2)
        res = await engine.search_routes(
            origin_code="BCT",
            destination_code="HWH",
            journey_date=journey_date,
            max_transfers=2,
            min_transfer_minutes=30,
            max_transfer_minutes=360,
        )

        assert res.query.max_transfers == 2
        two_transfer_routes = [r for r in res.routes if r.transfer_count == 2]

        assert len(two_transfer_routes) > 0
        route = two_transfer_routes[0]
        assert len(route.legs) == 3
        assert len(route.transfer_durations_minutes) == 2

        leg1, leg2, leg3 = route.legs
        # Verify chain continuity
        assert leg1.origin_code == "BCT"
        assert leg1.destination_code == leg2.origin_code
        assert leg2.destination_code == leg3.origin_code
        assert leg3.destination_code == "HWH"

        # Verify no station loops
        stations = {leg1.origin_code, leg1.destination_code, leg2.destination_code, leg3.destination_code}
        assert len(stations) == 4

        # Verify no train reuse
        assert leg1.train_number != leg2.train_number
        assert leg2.train_number != leg3.train_number
        assert leg1.train_number != leg3.train_number

        # Verify layover buffers
        t1_dur, t2_dur = route.transfer_durations_minutes
        assert 30 <= t1_dur <= 360
        assert 30 <= t2_dur <= 360

        # Verify chronological timing
        assert leg1.departure_time < leg1.arrival_time
        assert leg1.arrival_time <= leg2.departure_time
        assert leg2.departure_time < leg2.arrival_time
        assert leg2.arrival_time <= leg3.departure_time
        assert leg3.departure_time < leg3.arrival_time


@pytest.mark.asyncio
async def test_direct_and_one_transfer_preserved_with_two_transfers():
    """Verify that allowing 2 transfers does not displace or alter direct and 1-transfer routes."""
    async with AsyncSessionLocal() as session:
        engine = RouteDiscoveryEngine(session)
        journey_date = datetime.date(2026, 11, 3)

        # 1-transfer search baseline
        res1 = await engine.search_routes(
            origin_code="BCT",
            destination_code="NDLS",
            journey_date=journey_date,
            max_transfers=1,
        )
        base_direct_count = res1.direct_routes_count

        # 2-transfer search
        res2 = await engine.search_routes(
            origin_code="BCT",
            destination_code="NDLS",
            journey_date=journey_date,
            max_transfers=2,
        )

        assert res2.direct_routes_count == base_direct_count
        assert res2.total_routes_found >= res1.total_routes_found
        # The recommended top route should remain the direct service
        assert res2.routes[0].is_direct is True
