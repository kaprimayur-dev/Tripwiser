"""
Unit tests for the RouteDiscoveryEngine and journey discovery logic.
"""

import pytest
import datetime
from unittest.mock import AsyncMock, MagicMock

from app.domain.models.station import Station
from app.domain.models.train import Train, TrainScheduleEntry
from app.domain.models.route import CandidateRoute, JourneyLeg
from app.domain.models.availability import AvailabilityStatusCode
from app.domain.services.route_engine import RouteDiscoveryEngine, RouteSearchQuery


class TestRouteDiscoveryEngineUnit:
    """Verifies operating day matching, day offsets, transfer buffers, and route ranking."""

    def test_build_journey_leg_operating_day_with_day_offset(self):
        engine = RouteDiscoveryEngine(session=MagicMock())

        # Train runs only on Wednesdays (weekday 2)
        # Origin GWL (day_offset 0, dep 10:00)
        # Intermediate BPL (day_offset 1, arr 02:00, dep 02:15)
        # Destination NGP (day_offset 1, arr 08:00)
        stops = [
            TrainScheduleEntry(station_code="GWL", stop_sequence=1, departure_time=datetime.time(10, 0), day_offset=0, distance_km=0.0),
            TrainScheduleEntry(station_code="BPL", stop_sequence=2, arrival_time=datetime.time(2, 0), departure_time=datetime.time(2, 15), day_offset=1, distance_km=400.0),
            TrainScheduleEntry(station_code="NGP", stop_sequence=3, arrival_time=datetime.time(8, 0), day_offset=1, distance_km=800.0),
        ]
        train = Train(
            number="12999",
            name="Weekly Superfast",
            origin_code="GWL",
            destination_code="NGP",
            runs_on_days=[2],  # Wednesday only
            schedule=stops,
        )

        # 1. Searching from GWL on Wednesday (2026-11-04 is a Wednesday, weekday=2)
        wednesday = datetime.date(2026, 11, 4)
        assert wednesday.weekday() == 2

        leg_gwl = engine._build_journey_leg(train, "GWL", "NGP", wednesday)
        assert leg_gwl is not None
        assert leg_gwl.departure_time == datetime.datetime(2026, 11, 4, 10, 0)
        assert leg_gwl.arrival_time == datetime.datetime(2026, 11, 5, 8, 0)
        assert leg_gwl.duration_minutes == 22 * 60  # 10:00 Wed to 08:00 Thu = 22 hours
        assert leg_gwl.distance_km == 800.0
        assert leg_gwl.availability is None
        assert leg_gwl.travel_class is None

        # 2. Searching from BPL on Thursday (2026-11-05 is a Thursday, weekday=3)
        # Since BPL day_offset is 1, train started from GWL on Wednesday (3 - 1 = 2) -> MATCH!
        thursday = datetime.date(2026, 11, 5)
        assert thursday.weekday() == 3

        leg_bpl = engine._build_journey_leg(train, "BPL", "NGP", thursday)
        assert leg_bpl is not None
        assert leg_bpl.departure_time == datetime.datetime(2026, 11, 5, 2, 15)
        assert leg_bpl.arrival_time == datetime.datetime(2026, 11, 5, 8, 0)
        assert leg_bpl.duration_minutes == 5 * 60 + 45  # 02:15 to 08:00 = 5h 45m
        assert leg_bpl.distance_km == 400.0

        # 3. Searching from BPL on Wednesday (2026-11-04) -> Day offset 1 means origin was Tuesday (1) -> NO MATCH!
        leg_bpl_invalid = engine._build_journey_leg(train, "BPL", "NGP", wednesday)
        assert leg_bpl_invalid is None

    def test_overnight_journey_duration_and_day_rollover(self):
        engine = RouteDiscoveryEngine(session=MagicMock())

        # Departs 22:30 on Day 0, Arrives 06:15 on Day 1
        stops = [
            TrainScheduleEntry(station_code="NDLS", stop_sequence=1, departure_time=datetime.time(22, 30), day_offset=0, distance_km=0.0),
            TrainScheduleEntry(station_code="KOTA", stop_sequence=2, arrival_time=datetime.time(6, 15), day_offset=1, distance_km=465.0),
        ]
        train = Train(
            number="12402",
            name="Nanda Devi Express",
            origin_code="NDLS",
            destination_code="KOTA",
            runs_on_days=[0, 1, 2, 3, 4, 5, 6],
            schedule=stops,
        )

        journey_date = datetime.date(2026, 11, 10)
        leg = engine._build_journey_leg(train, "NDLS", "KOTA", journey_date)
        assert leg is not None
        assert leg.departure_time == datetime.datetime(2026, 11, 10, 22, 30)
        assert leg.arrival_time == datetime.datetime(2026, 11, 11, 6, 15)
        assert leg.duration_minutes == 465  # 7 hours 45 mins = 465 mins

    def test_route_ranking_fastest_vs_fewest_transfers_vs_recommended(self):
        engine = RouteDiscoveryEngine(session=MagicMock())
        now = datetime.datetime(2026, 11, 1, 10, 0)

        # Route A: Direct train, duration 600 mins (10 hours)
        leg_a = JourneyLeg(
            train_number="T1", train_name="Direct", origin_code="A", destination_code="C",
            departure_time=now, arrival_time=now + datetime.timedelta(minutes=600),
            duration_minutes=600, travel_class=None, distance_km=500.0,
            availability=None
        )
        route_direct = CandidateRoute(
            route_id="r_direct", legs=[leg_a], total_duration_minutes=600, total_fare=None,
            transfer_count=0, transfer_durations_minutes=[], is_direct=True, score=600.0
        )

        # Route B: 1-transfer route, total duration 500 mins (faster than direct, but has transfer)
        # Leg B1: 200 mins, Transfer: 60 mins, Leg B2: 240 mins (total = 500 mins)
        t_b1_arr = now + datetime.timedelta(minutes=200)
        t_b2_dep = t_b1_arr + datetime.timedelta(minutes=60)
        t_b2_arr = t_b2_dep + datetime.timedelta(minutes=240)
        leg_b1 = JourneyLeg(
            train_number="T2", train_name="Leg 1", origin_code="A", destination_code="B",
            departure_time=now, arrival_time=t_b1_arr, duration_minutes=200, travel_class=None, distance_km=250.0,
            availability=None
        )
        leg_b2 = JourneyLeg(
            train_number="T3", train_name="Leg 2", origin_code="B", destination_code="C",
            departure_time=t_b2_dep, arrival_time=t_b2_arr, duration_minutes=240, travel_class=None, distance_km=250.0,
            availability=None
        )
        route_transfer = CandidateRoute(
            route_id="r_transfer", legs=[leg_b1, leg_b2], total_duration_minutes=500, total_fare=None,
            transfer_count=1, transfer_durations_minutes=[60], is_direct=False, score=500.0 + 180.0
        )

        # 1. Ranking by "fastest": Route B (500m) should be first, Route A (600m) second
        fastest = engine._rank_routes([route_direct, route_transfer], sort_by="fastest")
        assert fastest[0].route_id == "r_transfer"
        assert fastest[1].route_id == "r_direct"

        # 2. Ranking by "fewest_transfers": Route A (0 transfers) should be first, Route B (1 transfer) second
        fewest = engine._rank_routes([route_direct, route_transfer], sort_by="fewest_transfers")
        assert fewest[0].route_id == "r_direct"
        assert fewest[1].route_id == "r_transfer"

        # 3. Ranking by "recommended": Direct route (score=600) beats transfer route (score=500 + 180 = 680)
        recommended = engine._rank_routes([route_direct, route_transfer], sort_by="recommended")
        assert recommended[0].route_id == "r_direct"
        assert recommended[1].route_id == "r_transfer"

        # 4. Ranking by "cheapest": Fares deferred, falls back to recommended ranking
        cheapest = engine._rank_routes([route_direct, route_transfer], sort_by="cheapest")
        assert cheapest[0].route_id == "r_direct"
        assert cheapest[1].route_id == "r_transfer"

    def test_unverified_commercial_data_never_fabricated(self):
        engine = RouteDiscoveryEngine(session=MagicMock())
        stops = [
            TrainScheduleEntry(
                station_code="NDLS", station_name="New Delhi", arrival_time=None,
                departure_time=datetime.time(6, 0), stop_sequence=1, day_offset=0, distance_km=0.0
            ),
            TrainScheduleEntry(
                station_code="BPL", station_name="Bhopal", arrival_time=datetime.time(14, 0),
                departure_time=None, stop_sequence=2, day_offset=0, distance_km=700.0
            ),
        ]
        train = Train(
            number="12001",
            name="Shatabdi",
            origin_code="NDLS",
            destination_code="BPL",
            runs_on_days=[0, 1, 2, 3, 4, 5, 6],
            schedule=stops,
        )

        leg = engine._build_journey_leg(train, "NDLS", "BPL", datetime.date(2026, 11, 2))
        assert leg is not None
        # Must never fabricate fare, seat availability, travel class or quota
        assert leg.availability is None
        assert leg.travel_class is None

    @pytest.mark.asyncio
    async def test_search_routes_same_origin_destination(self):
        engine = RouteDiscoveryEngine(session=MagicMock())
        result = await engine.search_routes("NDLS", "NDLS", datetime.date(2026, 11, 1))
        assert result.no_route_reason == "SAME_ORIGIN_DESTINATION"
        assert len(result.routes) == 0

    @pytest.mark.asyncio
    async def test_search_routes_station_not_found(self):
        mock_session = MagicMock()
        engine = RouteDiscoveryEngine(session=mock_session)
        engine.station_repo.get_by_code = AsyncMock(return_value=None)

        result = await engine.search_routes("INVALID1", "INVALID2", datetime.date(2026, 11, 1))
        assert result.no_route_reason == "STATION_NOT_FOUND"
        assert len(result.routes) == 0

