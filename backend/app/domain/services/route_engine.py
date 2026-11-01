"""
Route Discovery Engine for TripWiser.

Discovers direct and 1-transfer connecting railway journeys between origin and destination stations,
enforcing train operating days, schedule day offsets, transfer feasibility buffers, and route rankings.
"""

from typing import List, Optional, Tuple, Sequence, Dict, Any, Set
from dataclasses import dataclass, field
import datetime
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.station import Station
from app.domain.models.train import Train, TrainScheduleEntry
from app.domain.models.route import JourneyLeg, CandidateRoute
from app.domain.models.availability import AvailabilityResult, AvailabilityStatusCode
from app.domain.models.network import TrainConnectivity, StationConnectivityResult, InterchangeStation
from app.infrastructure.database.models.train import TrainORM, ScheduleORM
from app.infrastructure.database.models.station import StationORM
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

        # 4. Discover 2-Transfer Routes (if permitted)
        if max_transfers >= 2:
            two_transfer_routes = await self._find_two_transfer_routes(
                origin_code=orig_clean,
                destination_code=dest_clean,
                journey_date=journey_date,
                min_transfer_minutes=min_transfer_minutes,
                max_transfer_minutes=max_transfer_minutes,
            )
            candidate_routes.extend(two_transfer_routes)

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

    async def _find_candidate_hub_pairs(
        self, origin_code: str, destination_code: str, limit: int = 15
    ) -> List[Tuple[str, str]]:
        """
        Fast SQL join finding ordered intermediate station pairs (hub1, hub2)
        reachable via 3 connecting train services without loops.
        """
        sql = text(
            """
            SELECT s_hub1.station_code AS hub1, s_hub2.station_code AS hub2, COUNT(*) AS connection_count
            FROM train_schedules s_orig
            JOIN train_schedules s_hub1
                ON s_orig.train_number = s_hub1.train_number
                AND s_orig.station_code = :origin_code
                AND s_orig.stop_sequence < s_hub1.stop_sequence
            JOIN train_schedules s_mid1
                ON s_hub1.station_code = s_mid1.station_code
            JOIN train_schedules s_hub2
                ON s_mid1.train_number = s_hub2.train_number
                AND s_mid1.stop_sequence < s_hub2.stop_sequence
            JOIN train_schedules s_mid2
                ON s_hub2.station_code = s_mid2.station_code
            JOIN train_schedules s_dest
                ON s_mid2.train_number = s_dest.train_number
                AND s_dest.station_code = :destination_code
                AND s_mid2.stop_sequence < s_dest.stop_sequence
            WHERE s_orig.train_number != s_mid1.train_number
              AND s_mid1.train_number != s_mid2.train_number
              AND s_hub1.station_code NOT IN (:origin_code, :destination_code)
              AND s_hub2.station_code NOT IN (:origin_code, :destination_code)
              AND s_hub1.station_code != s_hub2.station_code
            GROUP BY s_hub1.station_code, s_hub2.station_code
            ORDER BY connection_count DESC
            LIMIT :limit;
            """
        )
        res = await self.session.execute(
            sql,
            {
                "origin_code": origin_code,
                "destination_code": destination_code,
                "limit": limit,
            },
        )
        return [(row[0], row[1]) for row in res.fetchall()]

    async def _find_two_transfer_routes(
        self,
        origin_code: str,
        destination_code: str,
        journey_date: datetime.date,
        min_transfer_minutes: int,
        max_transfer_minutes: int,
        limit_hub_pairs: int = 15,
        max_routes_per_search: int = 20,
    ) -> List[CandidateRoute]:
        """
        Discovers 2-transfer (3-leg) routes connecting origin to destination via two intermediate hubs.
        Enforces strict loop prevention (origin != hub1 != hub2 != destination), distinct train services,
        realistic layovers, and honest operating calendars.
        """
        hub_pairs = await self._find_candidate_hub_pairs(
            origin_code, destination_code, limit=limit_hub_pairs
        )
        two_transfer_routes: List[CandidateRoute] = []
        seen_signatures: Set[Tuple[str, str, str, datetime.datetime, datetime.datetime]] = set()

        # Cache direct train lookups per station pair to avoid repeated queries
        train_cache: Dict[Tuple[str, str], List[Train]] = {}

        async def get_cached_trains(st_from: str, st_to: str) -> List[Train]:
            key = (st_from, st_to)
            if key not in train_cache:
                train_cache[key] = await self.train_repo.find_direct_trains(st_from, st_to)
            return train_cache[key]

        for hub1_code, hub2_code in hub_pairs:
            # Enforce distinct stations (no loops)
            if len({origin_code, hub1_code, hub2_code, destination_code}) != 4:
                continue

            leg1_trains = await get_cached_trains(origin_code, hub1_code)
            leg2_trains = await get_cached_trains(hub1_code, hub2_code)
            leg3_trains = await get_cached_trains(hub2_code, destination_code)

            if not leg1_trains or not leg2_trains or not leg3_trains:
                continue

            for t1 in leg1_trains:
                leg1 = self._build_journey_leg(
                    train=t1,
                    origin_code=origin_code,
                    destination_code=hub1_code,
                    departure_date=journey_date,
                )
                if leg1 is None:
                    continue

                hub1_arr_dt = leg1.arrival_time

                for t2 in leg2_trains:
                    if t2.number == t1.number:
                        continue

                    cand_dep2_dates = [
                        hub1_arr_dt.date(),
                        hub1_arr_dt.date() + datetime.timedelta(days=1),
                    ]

                    for dep2_date in cand_dep2_dates:
                        leg2 = self._build_journey_leg(
                            train=t2,
                            origin_code=hub1_code,
                            destination_code=hub2_code,
                            departure_date=dep2_date,
                        )
                        if leg2 is None:
                            continue

                        t1_mins = int((leg2.departure_time - hub1_arr_dt).total_seconds() // 60)
                        if not (min_transfer_minutes <= t1_mins <= max_transfer_minutes):
                            continue

                        hub2_arr_dt = leg2.arrival_time

                        for t3 in leg3_trains:
                            if t3.number in (t1.number, t2.number):
                                continue

                            cand_dep3_dates = [
                                hub2_arr_dt.date(),
                                hub2_arr_dt.date() + datetime.timedelta(days=1),
                            ]

                            for dep3_date in cand_dep3_dates:
                                leg3 = self._build_journey_leg(
                                    train=t3,
                                    origin_code=hub2_code,
                                    destination_code=destination_code,
                                    departure_date=dep3_date,
                                )
                                if leg3 is None:
                                    continue

                                t2_mins = int((leg3.departure_time - hub2_arr_dt).total_seconds() // 60)
                                if not (min_transfer_minutes <= t2_mins <= max_transfer_minutes):
                                    continue

                                sig = (
                                    t1.number,
                                    t2.number,
                                    t3.number,
                                    leg1.departure_time,
                                    leg3.arrival_time,
                                )
                                if sig in seen_signatures:
                                    continue
                                seen_signatures.add(sig)

                                total_duration = (
                                    leg1.duration_minutes
                                    + t1_mins
                                    + leg2.duration_minutes
                                    + t2_mins
                                    + leg3.duration_minutes
                                )
                                route_id = (
                                    f"route_{t1.number}_{t2.number}_{t3.number}_{hub1_code}_{hub2_code}_"
                                    f"{journey_date.strftime('%Y%m%d')}"
                                )
                                route = CandidateRoute(
                                    route_id=route_id,
                                    legs=[leg1, leg2, leg3],
                                    total_duration_minutes=total_duration,
                                    total_fare=None,
                                    transfer_count=2,
                                    transfer_durations_minutes=[t1_mins, t2_mins],
                                    is_direct=False,
                                    score=float(total_duration + 360),
                                )
                                two_transfer_routes.append(route)
                                if len(two_transfer_routes) >= max_routes_per_search:
                                    return two_transfer_routes

        return two_transfer_routes

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

        # Count intermediate commercial halts
        intermediate_count = sum(
            1 for s in train.schedule
            if orig_stop.stop_sequence < s.stop_sequence < dest_stop.stop_sequence
            and (
                (s.arrival_time and s.departure_time and s.arrival_time != s.departure_time)
                or (s.arrival_time is None or s.departure_time is None)
            )
        )

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
            runs_on_days=train.runs_on_days,
            intermediate_stop_count=intermediate_count,
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

    async def get_station_connectivity(
        self, origin_code: str, destination_code: str
    ) -> StationConnectivityResult:
        """
        Returns all compiled direct trains connecting origin and destination stations,
        including departure/arrival timings, durations, distances, running days, and intermediate halt counts.
        """
        orig_clean = origin_code.strip().upper()
        dest_clean = destination_code.strip().upper()
        result = StationConnectivityResult(origin_code=orig_clean, destination_code=dest_clean)

        candidate_trains = await self.train_repo.find_direct_trains(orig_clean, dest_clean)
        train_connectivities: List[TrainConnectivity] = []

        for train in candidate_trains:
            sched_map = {s.station_code: s for s in train.schedule}
            orig_stop = sched_map.get(orig_clean)
            dest_stop = sched_map.get(dest_clean)
            if not orig_stop or not dest_stop:
                continue
            if orig_stop.stop_sequence >= dest_stop.stop_sequence:
                continue
            if orig_stop.departure_time is None or dest_stop.arrival_time is None:
                continue

            day_diff = dest_stop.day_offset - orig_stop.day_offset
            base_date = datetime.date(2000, 1, 1)
            dep_dt = datetime.datetime.combine(base_date, orig_stop.departure_time)
            arr_dt = datetime.datetime.combine(
                base_date + datetime.timedelta(days=day_diff),
                dest_stop.arrival_time,
            )
            duration_minutes = int((arr_dt - dep_dt).total_seconds() // 60)
            if duration_minutes < 0:
                continue

            distance_km = float(dest_stop.distance_km - orig_stop.distance_km)
            if distance_km < 0:
                distance_km = float(dest_stop.distance_km)

            intermediate_count = sum(
                1 for s in train.schedule
                if orig_stop.stop_sequence < s.stop_sequence < dest_stop.stop_sequence
            )

            train_connectivities.append(
                TrainConnectivity(
                    train_number=train.number,
                    train_name=train.name,
                    origin_code=orig_clean,
                    destination_code=dest_clean,
                    departure_time=orig_stop.departure_time,
                    arrival_time=dest_stop.arrival_time,
                    day_difference=day_diff,
                    duration_minutes=duration_minutes,
                    distance_km=distance_km,
                    runs_on_days=train.runs_on_days,
                    intermediate_stop_count=intermediate_count,
                    origin_stop_sequence=orig_stop.stop_sequence,
                    destination_stop_sequence=dest_stop.stop_sequence,
                )
            )

        train_connectivities.sort(key=lambda tc: (tc.departure_time, tc.duration_minutes))

        result.trains = train_connectivities
        result.total_trains_count = len(train_connectivities)
        if train_connectivities:
            result.fastest_duration_minutes = min(tc.duration_minutes for tc in train_connectivities)
            result.average_duration_minutes = int(
                sum(tc.duration_minutes for tc in train_connectivities) / len(train_connectivities)
            )

        return result

    async def get_interchanges(
        self,
        origin_code: Optional[str] = None,
        destination_code: Optional[str] = None,
        limit: int = 20,
    ) -> List[InterchangeStation]:
        """
        Discovers interchange junction stations.
        When origin and destination are specified, returns transfer hubs connecting services between them.
        When not specified, returns top network-wide interchange hubs by calling train frequency.
        """
        interchanges: List[InterchangeStation] = []

        if origin_code and destination_code:
            orig_clean = origin_code.strip().upper()
            dest_clean = destination_code.strip().upper()

            sql = text(
                """
                SELECT 
                    s.station_code,
                    COUNT(DISTINCT s.train_number) AS inbound_count,
                    COUNT(DISTINCT s_out.train_number) AS outbound_count,
                    array_agg(DISTINCT s.train_number) AS inbound_trains,
                    array_agg(DISTINCT s_out.train_number) AS outbound_trains
                FROM train_schedules s
                JOIN train_schedules s_orig
                    ON s.train_number = s_orig.train_number
                    AND s_orig.station_code = :origin_code
                    AND s_orig.stop_sequence < s.stop_sequence
                JOIN train_schedules s_out
                    ON s.station_code = s_out.station_code
                JOIN train_schedules s_dest
                    ON s_out.train_number = s_dest.train_number
                    AND s_dest.station_code = :destination_code
                    AND s_out.stop_sequence < s_dest.stop_sequence
                WHERE s.station_code NOT IN (:origin_code, :destination_code)
                  AND s.train_number != s_out.train_number
                GROUP BY s.station_code
                ORDER BY (COUNT(DISTINCT s.train_number) * COUNT(DISTINCT s_out.train_number)) DESC
                LIMIT :limit;
                """
            )
            res = await self.session.execute(
                sql,
                {"origin_code": orig_clean, "destination_code": dest_clean, "limit": limit},
            )
            rows = res.fetchall()
            codes = [r[0] for r in rows]
            st_map = {s.code: s for s in await self.station_repo.get_by_codes(codes)}

            for r in rows:
                code, in_cnt, out_cnt, in_sample, out_sample = r
                st = st_map.get(code)
                if not st:
                    continue
                score = in_cnt * out_cnt
                interchanges.append(
                    InterchangeStation(
                        station_code=code,
                        station_name=st.name,
                        city=st.city,
                        state=st.state,
                        zone=st.zone,
                        latitude=st.latitude,
                        longitude=st.longitude,
                        inbound_trains_count=in_cnt,
                        outbound_trains_count=out_cnt,
                        connection_score=score,
                        sample_inbound_trains=list(in_sample[:4]) if in_sample else [],
                        sample_outbound_trains=list(out_sample[:4]) if out_sample else [],
                    )
                )
        else:
            # Global network interchange hubs
            sql = text(
                """
                SELECT 
                    s.station_code,
                    COUNT(DISTINCT s.train_number) AS calling_trains,
                    array_agg(DISTINCT s.train_number) AS sample_trains
                FROM train_schedules s
                GROUP BY s.station_code
                HAVING COUNT(DISTINCT s.train_number) >= 2
                ORDER BY calling_trains DESC
                LIMIT :limit;
                """
            )
            res = await self.session.execute(sql, {"limit": limit})
            rows = res.fetchall()
            codes = [r[0] for r in rows]
            st_map = {s.code: s for s in await self.station_repo.get_by_codes(codes)}

            for r in rows:
                code, calling_cnt, sample = r
                st = st_map.get(code)
                if not st:
                    continue
                interchanges.append(
                    InterchangeStation(
                        station_code=code,
                        station_name=st.name,
                        city=st.city,
                        state=st.state,
                        zone=st.zone,
                        latitude=st.latitude,
                        longitude=st.longitude,
                        inbound_trains_count=calling_cnt,
                        outbound_trains_count=calling_cnt,
                        connection_score=calling_cnt,
                        sample_inbound_trains=list(sample[:4]) if sample else [],
                        sample_outbound_trains=list(sample[:4]) if sample else [],
                    )
                )

        return interchanges

