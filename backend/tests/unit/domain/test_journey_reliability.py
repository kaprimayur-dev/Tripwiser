"""
Unit and integration tests for TW-113:
Journey Reliability & Transfer Risk Intelligence:
- Journey time breakdown (total duration = travel time + wait time)
- 5-tier transfer risk classification
- Factual deterministic journey insights
- Overnight and multi-transfer layovers
"""

import pytest
import datetime

from app.core.db import AsyncSessionLocal
from app.domain.services.route_engine import RouteDiscoveryEngine
from app.domain.models.route import TransferRiskLevel, JourneyLeg, CandidateRoute


def test_transfer_risk_classification_boundaries():
    """Verify exact boundary classifications for all 5 connection risk categories."""
    base_arr = datetime.datetime(2026, 11, 2, 10, 0)

    # 1. Below 30 mins: INVALID_CONNECTION
    layover_29 = RouteDiscoveryEngine.classify_transfer_layover(
        station_code="TEST",
        arriving_train_number="11111",
        departing_train_number="22222",
        arrival_time=base_arr,
        departure_time=base_arr + datetime.timedelta(minutes=29),
        duration_minutes=29,
    )
    assert layover_29.risk_level == TransferRiskLevel.INVALID_CONNECTION
    assert layover_29.risk_label == "Invalid Connection"
    assert "below the 30-minute minimum buffer" in layover_29.risk_description

    # 2. 30-44 mins: TIGHT_CONNECTION (both endpoints)
    layover_30 = RouteDiscoveryEngine.classify_transfer_layover(
        station_code="TEST",
        arriving_train_number="11111",
        departing_train_number="22222",
        arrival_time=base_arr,
        departure_time=base_arr + datetime.timedelta(minutes=30),
        duration_minutes=30,
    )
    assert layover_30.risk_level == TransferRiskLevel.TIGHT_CONNECTION
    assert layover_30.risk_label == "Tight Connection"

    layover_44 = RouteDiscoveryEngine.classify_transfer_layover(
        station_code="TEST",
        arriving_train_number="11111",
        departing_train_number="22222",
        arrival_time=base_arr,
        departure_time=base_arr + datetime.timedelta(minutes=44),
        duration_minutes=44,
    )
    assert layover_44.risk_level == TransferRiskLevel.TIGHT_CONNECTION
    assert layover_44.risk_label == "Tight Connection"

    # 3. 45-89 mins: MODERATE_CONNECTION (both endpoints)
    layover_45 = RouteDiscoveryEngine.classify_transfer_layover(
        station_code="TEST",
        arriving_train_number="11111",
        departing_train_number="22222",
        arrival_time=base_arr,
        departure_time=base_arr + datetime.timedelta(minutes=45),
        duration_minutes=45,
    )
    assert layover_45.risk_level == TransferRiskLevel.MODERATE_CONNECTION
    assert layover_45.risk_label == "Moderate Connection"

    layover_89 = RouteDiscoveryEngine.classify_transfer_layover(
        station_code="TEST",
        arriving_train_number="11111",
        departing_train_number="22222",
        arrival_time=base_arr,
        departure_time=base_arr + datetime.timedelta(minutes=89),
        duration_minutes=89,
    )
    assert layover_89.risk_level == TransferRiskLevel.MODERATE_CONNECTION
    assert layover_89.risk_label == "Moderate Connection"

    # 4. 90-180 mins: COMFORTABLE_CONNECTION (both endpoints)
    layover_90 = RouteDiscoveryEngine.classify_transfer_layover(
        station_code="TEST",
        arriving_train_number="11111",
        departing_train_number="22222",
        arrival_time=base_arr,
        departure_time=base_arr + datetime.timedelta(minutes=90),
        duration_minutes=90,
    )
    assert layover_90.risk_level == TransferRiskLevel.COMFORTABLE_CONNECTION
    assert layover_90.risk_label == "Comfortable Connection"

    layover_180 = RouteDiscoveryEngine.classify_transfer_layover(
        station_code="TEST",
        arriving_train_number="11111",
        departing_train_number="22222",
        arrival_time=base_arr,
        departure_time=base_arr + datetime.timedelta(minutes=180),
        duration_minutes=180,
    )
    assert layover_180.risk_level == TransferRiskLevel.COMFORTABLE_CONNECTION
    assert layover_180.risk_label == "Comfortable Connection"

    # 5. Above 180 mins: LONG_WAIT
    layover_181 = RouteDiscoveryEngine.classify_transfer_layover(
        station_code="TEST",
        arriving_train_number="11111",
        departing_train_number="22222",
        arrival_time=base_arr,
        departure_time=base_arr + datetime.timedelta(minutes=181),
        duration_minutes=181,
    )
    assert layover_181.risk_level == TransferRiskLevel.LONG_WAIT
    assert layover_181.risk_label == "Long Wait"


@pytest.mark.asyncio
async def test_direct_journey_breakdown():
    """Verify direct route has 0 waiting time, 100% travel time, empty layovers, and direct insights."""
    async with AsyncSessionLocal() as session:
        engine = RouteDiscoveryEngine(session)
        res = await engine.search_routes(
            origin_code="NDLS",
            destination_code="BPL",
            journey_date=datetime.date(2026, 11, 2),
            max_transfers=0,
        )

        assert res.total_routes_found > 0
        direct_routes = [r for r in res.routes if r.is_direct]
        assert len(direct_routes) > 0

        route = direct_routes[0]
        assert route.transfer_count == 0
        assert route.total_travel_time_minutes == route.total_duration_minutes
        assert route.total_wait_time_minutes == 0
        assert len(route.layovers) == 0
        assert route.overall_transfer_risk is None

        # Check insights
        assert any("Direct service" in insight for insight in route.insights)
        assert any("100% of journey duration" in insight for insight in route.insights)


@pytest.mark.asyncio
async def test_one_transfer_breakdown_and_risk():
    """Verify 1-transfer route correctly computes travel time, layover, risk classification and insights."""
    async with AsyncSessionLocal() as session:
        engine = RouteDiscoveryEngine(session)
        res = await engine.search_routes(
            origin_code="BCT",
            destination_code="NDLS",
            journey_date=datetime.date(2026, 11, 2),
            max_transfers=1,
        )

        connecting_routes = [r for r in res.routes if not r.is_direct and r.transfer_count == 1]
        if connecting_routes:
            route = connecting_routes[0]
            assert route.total_duration_minutes == route.total_travel_time_minutes + route.total_wait_time_minutes
            assert len(route.layovers) == 1
            layover = route.layovers[0]
            assert layover.duration_minutes == route.total_wait_time_minutes
            assert layover.interchange_station_code == route.legs[0].destination_code
            assert layover.arriving_train_number == route.legs[0].train_number
            assert layover.departing_train_number == route.legs[1].train_number
            assert layover.risk_level in [
                TransferRiskLevel.TIGHT_CONNECTION,
                TransferRiskLevel.MODERATE_CONNECTION,
                TransferRiskLevel.COMFORTABLE_CONNECTION,
                TransferRiskLevel.LONG_WAIT,
            ]
            assert route.overall_transfer_risk == layover.risk_level.value
            assert any("1 transfer" in ins for ins in route.insights)


@pytest.mark.asyncio
async def test_two_transfer_breakdown_and_overall_risk():
    """Verify 2-transfer route has 2 distinct layovers and overall risk reflects highest risk leg."""
    async with AsyncSessionLocal() as session:
        engine = RouteDiscoveryEngine(session)
        res = await engine.search_routes(
            origin_code="BCT",
            destination_code="HWH",
            journey_date=datetime.date(2026, 11, 2),
            max_transfers=2,
        )

        two_transfer_routes = [r for r in res.routes if r.transfer_count == 2]
        assert len(two_transfer_routes) > 0

        route = two_transfer_routes[0]
        assert len(route.legs) == 3
        assert len(route.layovers) == 2
        assert route.total_duration_minutes == route.total_travel_time_minutes + route.total_wait_time_minutes

        l1, l2 = route.layovers
        assert l1.duration_minutes == route.transfer_durations_minutes[0]
        assert l2.duration_minutes == route.transfer_durations_minutes[1]
        assert l1.interchange_station_code == route.legs[0].destination_code
        assert l2.interchange_station_code == route.legs[1].destination_code

        # If any layover is tight connection, overall risk must be tight connection
        if any(l.risk_level == TransferRiskLevel.TIGHT_CONNECTION for l in route.layovers):
            assert route.overall_transfer_risk == TransferRiskLevel.TIGHT_CONNECTION.value
