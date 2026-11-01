"""
Route Discovery Engine for TripWiser.

Discovers direct and 1-transfer connecting railway journeys between origin and destination stations,
enforcing train operating days, schedule day offsets, transfer feasibility buffers, and route rankings.
"""

from typing import List, Optional, Tuple, Sequence, Dict, Any
from dataclasses import dataclass, field
import datetime
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.station import Station
from app.domain.models.train import Train, TrainScheduleEntry
from app.domain.models.route import JourneyLeg, CandidateRoute
from app.domain.models.availability import AvailabilityResult, AvailabilityStatusCode
from app.infrastructure.database.models.train import TrainORM, ScheduleORM
from app.infrastructure.database.repositories.station_repository import SQLAlchemyStationRepository
from app.infrastructure.database.repositories.train_repository import SQLAlchemyTrainRepository


@dataclass
class RouteSearchQuery:
    origin_code: str
    destination_code: str
    journey_date: datetime.date
    max_transfers: int = 1
    sort_by: str = "recommended"
    min_transfer_minutes: int = 30
    max_transfer_minutes: int = 360


@dataclass
class RouteSearchResult:
    query: RouteSearchQuery
    origin_station: Optional[Station] = None
    destination_station: Optional[Station] = None
    routes: List[CandidateRoute] = field(default_factory=list)
    total_routes_found: int = 0
    direct_routes_count: int = 0
    transfer_routes_count: int = 0
    no_route_reason: Optional[str] = None
    timetable_status: str = "TIMETABLE_CONFIRMED"
    fare_status: str = "DEFERRED_NO_COMMERCIAL_FEED"
    availability_status: str = "NOT_CHECKED_SEAT_AVAILABILITY_DEFERRED"
    sorting_applied: str = "recommended"
    sorting_note: Optional[str] = None


class RouteDiscoveryEngine:
    """
    Core route finding engine supporting direct and multi-leg railway discovery.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.station_repo = SQLAlchemyStationRepository(session)
        self.train_repo = SQLAlchemyTrainRepository(session)

    async def search_routes(
        self,
        origin_code: str,
        destination_code: str,
        journey_date: datetime.date,
        max_transfers: int = 1,
        sort_by: str = "recommended",
        min_transfer_minutes: int = 30,
        max_transfer_minutes: int = 360,
        limit: int = 20,
    ) -> RouteSearchResult:
        """
        Main entry point for journey discovery.
        """
        orig_clean = origin_code.strip().upper()
        dest_clean = destination_code.strip().upper()

        query = RouteSearchQuery(
            origin_code=orig_clean,
            destination_code=dest_clean,
            journey_date=journey_date,
            max_transfers=max_transfers,
            sort_by=sort_by.lower(),
            min_transfer_minutes=min_transfer_minutes,
            max_transfer_minutes=max_transfer_minutes,
        )

        result = RouteSearchResult(query=query)

        # 1. Endpoint Validation
        if orig_clean == dest_clean:
            result.no_route_reason = "SAME_ORIGIN_DESTINATION"
            return result

        origin_st = await self.station_repo.get_by_code(orig_clean)
        dest_st = await self.station_repo.get_by_code(dest_clean)
        result.origin_station = origin_st
        result.destination_station = dest_st

        if not origin_st or not dest_st:
            result.no_route_reason = "STATION_NOT_FOUND"
            return result

        candidate_routes: List[CandidateRoute] = []

        # 2. Discover Direct Routes
        direct_routes = await self._find_direct_routes(
            origin_code=orig_clean,
            destination_code=dest_clean,
            journey_date=journey_date,
        )
        candidate_routes.extend(direct_routes)

        # 3. Discover Connecting Routes (if permitted)
        if max_transfers >= 1:
            connecting_routes = await self._find_connecting_routes(
                origin_code=orig_clean,
                destination_code=dest_clean,
                journey_date=journey_date,
                min_transfer_minutes=min_transfer_minutes,
                max_transfer_minutes=max_transfer_minutes,
            )
            candidate_routes.extend(connecting_routes)

        # 4. Rank and Filter Routes
        sorting_applied = sort_by.lower()
        sorting_note = None
        if sorting_applied == "cheapest":
            sorting_applied = "recommended"
            sorting_note = "Cheapest sorting deferred: No verified commercial fare feed is available."

        result.sorting_applied = sorting_applied
        result.sorting_note = sorting_note

        ranked_routes = self._rank_routes(candidate_routes, sort_by=sorting_applied)
        result.routes = ranked_routes[:limit]
        result.total_routes_found = len(candidate_routes)
        result.direct_routes_count = len(direct_routes)
        result.transfer_routes_count = len(candidate_routes) - len(direct_routes)

        if not result.routes:
            # Diagnose empty reason
            all_direct_trains = await self.train_repo.find_direct_trains(orig_clean, dest_clean)
            if all_direct_trains:
                result.no_route_reason = "NO_RUNNING_DAYS_MATCH"
            else:
                candidate_hubs = await self._find_candidate_hubs(orig_clean, dest_clean)
                if candidate_hubs:
                    result.no_route_reason = "TRANSFER_BUFFER_VIOLATION"
                else:
                    result.no_route_reason = "NO_DIRECT_OR_CONNECTING_TRAINS"

        return result

    async def _find_direct_routes(
        self,
        origin_code: str,
        destination_code: str,
        journey_date: datetime.date,
    ) -> List[CandidateRoute]:
        """Discovers direct trains operating on journey_date."""
        candidate_trains = await self.train_repo.find_direct_trains(origin_code, destination_code)
        direct_routes: List[CandidateRoute] = []

        for train in candidate_trains:
            leg = self._build_journey_leg(
                train=train,
                origin_code=origin_code,
                destination_code=destination_code,
                departure_date=journey_date,
            )
            if leg is not None:
                route_id = f"route_direct_{train.number}_{journey_date.strftime('%Y%m%d')}"
                route = CandidateRoute(
                    route_id=route_id,
                    legs=[leg],
                    total_duration_minutes=leg.duration_minutes,
                    total_fare=None,
                    transfer_count=0,
                    transfer_durations_minutes=[],
                    is_direct=True,
                    score=float(leg.duration_minutes),
                )
                direct_routes.append(route)

        return direct_routes

    async def _find_connecting_routes(
        self,
        origin_code: str,
        destination_code: str,
        journey_date: datetime.date,
        min_transfer_minutes: int,
        max_transfer_minutes: int,
    ) -> List[CandidateRoute]:
        """Discovers 1-transfer routes via intermediate junction hubs."""
        hubs = await self._find_candidate_hubs(origin_code, destination_code)
        connecting_routes: List[CandidateRoute] = []

        for hub_code in hubs:
            leg1_trains = await self.train_repo.find_direct_trains(origin_code, hub_code)
            leg2_trains = await self.train_repo.find_direct_trains(hub_code, destination_code)

            for t1 in leg1_trains:
                leg1 = self._build_journey_leg(
                    train=t1,
                    origin_code=origin_code,
                    destination_code=hub_code,
                    departure_date=journey_date,
                )
                if leg1 is None:
                    continue

                hub_arrival_dt = leg1.arrival_time

                for t2 in leg2_trains:
                    if t1.number == t2.number:
                        continue

                    # Leg 2 can depart on the arrival date or next date
                    candidate_dep_dates = [
                        hub_arrival_dt.date(),
                        hub_arrival_dt.date() + datetime.timedelta(days=1),
                    ]

                    for leg2_dep_date in candidate_dep_dates:
                        leg2 = self._build_journey_leg(
                            train=t2,
                            origin_code=hub_code,
                            destination_code=destination_code,
                            departure_date=leg2_dep_date,
                        )
                        if leg2 is None:
                            continue

                        transfer_minutes = int(
                            (leg2.departure_time - hub_arrival_dt).total_seconds() // 60
                        )

                        if min_transfer_minutes <= transfer_minutes <= max_transfer_minutes:
                            total_duration = leg1.duration_minutes + transfer_minutes + leg2.duration_minutes
                            route_id = f"route_{t1.number}_{t2.number}_{hub_code}_{journey_date.strftime('%Y%m%d')}"
                            route = CandidateRoute(
                                route_id=route_id,
                                legs=[leg1, leg2],
                                total_duration_minutes=total_duration,
                                total_fare=None,
                                transfer_count=1,
                                transfer_durations_minutes=[transfer_minutes],
                                is_direct=False,
                                score=float(total_duration + 180),
                            )
                            connecting_routes.append(route)

        return connecting_routes

    async def _find_candidate_hubs(self, origin_code: str, destination_code: str) -> List[str]:
        """
        Fast SQL join finding intermediate stations reachable from origin
        and capable of reaching destination on another train.
        """
        sql = text(
            """
            SELECT s1.station_code AS hub_code, COUNT(*) AS connection_count
            FROM train_schedules s1
            JOIN train_schedules s_orig 
                ON s1.train_number = s_orig.train_number 
                AND s_orig.station_code = :origin_code 
                AND s_orig.stop_sequence < s1.stop_sequence
            JOIN train_schedules s2 
                ON s1.station_code = s2.station_code
            JOIN train_schedules s_dest 
                ON s2.train_number = s_dest.train_number 
                AND s_dest.station_code = :destination_code 
                AND s2.stop_sequence < s_dest.stop_sequence
            WHERE s1.train_number != s2.train_number
            GROUP BY s1.station_code
            ORDER BY connection_count DESC
            LIMIT 20;
            """
        )
        res = await self.session.execute(sql, {"origin_code": origin_code, "destination_code": destination_code})
        return [row[0] for row in res.fetchall()]

    def _build_journey_leg(
        self,
        train: Train,
        origin_code: str,
        destination_code: str,
        departure_date: datetime.date,
    ) -> Optional[JourneyLeg]:
        """
        Constructs a validated JourneyLeg if the train operates on departure_date at origin_code
        and complete departure/arrival times are available.
        """
        sched_map: Dict[str, TrainScheduleEntry] = {s.station_code: s for s in train.schedule}
        orig_stop = sched_map.get(origin_code)
        dest_stop = sched_map.get(destination_code)

        if not orig_stop or not dest_stop:
            return None

        if orig_stop.stop_sequence >= dest_stop.stop_sequence:
            return None

        if orig_stop.departure_time is None or dest_stop.arrival_time is None:
            return None

        # Check train operating days taking origin stop day_offset into account:
        # origin_date = departure_date - timedelta(days=orig_stop.day_offset)
        train_start_date = departure_date - datetime.timedelta(days=orig_stop.day_offset)
        train_start_weekday = train_start_date.weekday()

        if train_start_weekday not in train.runs_on_days:
            return None

        # Compute departure and arrival datetimes
        dep_datetime = datetime.datetime.combine(departure_date, orig_stop.departure_time)
        day_diff = dest_stop.day_offset - orig_stop.day_offset
        arr_datetime = datetime.datetime.combine(
            departure_date + datetime.timedelta(days=day_diff),
            dest_stop.arrival_time,
        )

        duration_minutes = int((arr_datetime - dep_datetime).total_seconds() // 60)
        if duration_minutes < 0:
            return None

        distance_km = float(dest_stop.distance_km - orig_stop.distance_km)
        if distance_km < 0:
            distance_km = float(dest_stop.distance_km)

        # Timetable route discovery does not fabricate live availability or commercial fares
        return JourneyLeg(
            train_number=train.number,
            train_name=train.name,
            origin_code=origin_code,
            destination_code=destination_code,
            departure_time=dep_datetime,
            arrival_time=arr_datetime,
            duration_minutes=duration_minutes,
            travel_class=None,
            distance_km=distance_km,
            availability=None,
        )

    def _rank_routes(self, routes: Sequence[CandidateRoute], sort_by: str) -> List[CandidateRoute]:
        """Ranks candidate routes according to the requested strategy."""
        route_list = list(routes)
        if not route_list:
            return []

        if sort_by == "fastest":
            route_list.sort(key=lambda r: (r.total_duration_minutes, r.transfer_count))
        elif sort_by == "fewest_transfers":
            route_list.sort(key=lambda r: (r.transfer_count, r.total_duration_minutes))
        else:  # recommended (default)
            def compute_recommended_score(r: CandidateRoute) -> float:
                score = float(r.total_duration_minutes)
                if r.is_direct:
                    return score

                # Penalty for transfer count
                score += 180.0 * r.transfer_count

                # Penalty for awkward transfer durations
                for dt in r.transfer_durations_minutes:
                    if dt < 45:
                        score += (45 - dt) * 2.0
                    elif dt > 120:
                        score += (dt - 120) * 0.5
                return score

            route_list.sort(key=compute_recommended_score)

        return route_list

