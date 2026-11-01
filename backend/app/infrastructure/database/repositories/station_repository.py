from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func, case
from geoalchemy2.functions import ST_DWithin, ST_Distance, ST_SetSRID, ST_MakePoint
from app.domain.repositories.station_repository import StationRepository
from app.domain.models.station import Station
from app.infrastructure.database.models.station import StationORM
from app.infrastructure.database.models.train import TrainORM, ScheduleORM

class SQLAlchemyStationRepository(StationRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_domain(self, orm: StationORM) -> Station:
        # Extract lat/lon coordinates from WKB/GeoJSON or point geometry
        # GeoAlchemy2 provides ST_X (lon) and ST_Y (lat) or spatial element
        return Station(
            code=orm.code,
            name=orm.name,
            latitude=0.0,  # Handled via ST_Y/ST_X in query or properties
            longitude=0.0,
            city=orm.city,
            state=orm.state,
            zone=orm.zone
        )

    async def get_by_code(self, code: str) -> Optional[Station]:
        stmt = select(
            StationORM,
            func.ST_Y(func.geometry(StationORM.location)).label("lat"),
            func.ST_X(func.geometry(StationORM.location)).label("lon")
        ).where(StationORM.code == code)
        
        result = await self.session.execute(stmt)
        row = result.first()
        if not row:
            return None
        
        orm, lat, lon = row
        return Station(
            code=orm.code,
            name=orm.name,
            latitude=float(lat),
            longitude=float(lon),
            city=orm.city,
            state=orm.state,
            zone=orm.zone
        )

    async def get_by_codes(self, codes: list[str]) -> list[Station]:
        if not codes:
            return []
        clean_codes = [c.strip().upper() for c in codes if c and c.strip()]
        if not clean_codes:
            return []

        stmt = select(
            StationORM,
            func.ST_Y(func.geometry(StationORM.location)).label("lat"),
            func.ST_X(func.geometry(StationORM.location)).label("lon")
        ).where(StationORM.code.in_(clean_codes))

        result = await self.session.execute(stmt)
        rows = result.all()
        return [
            Station(
                code=orm.code,
                name=orm.name,
                latitude=float(lat) if lat is not None else 0.0,
                longitude=float(lon) if lon is not None else 0.0,
                city=orm.city,
                state=orm.state,
                zone=orm.zone,
            )
            for orm, lat, lon in rows
        ]

    async def search_by_name_or_code(self, query: str, limit: int = 10) -> list[Station]:
        clean_q = query.strip().upper()
        if not clean_q:
            return []
        
        prefix_q = f"{clean_q}%"
        substr_q = f"%{clean_q}%"
        
        stmt = (
            select(
                StationORM,
                func.ST_Y(func.geometry(StationORM.location)).label("lat"),
                func.ST_X(func.geometry(StationORM.location)).label("lon")
            )
            .where(
                or_(
                    StationORM.code.ilike(substr_q),
                    StationORM.name.ilike(substr_q),
                    StationORM.city.ilike(substr_q)
                )
            )
            .order_by(
                case(
                    (func.upper(StationORM.code) == clean_q, 0),
                    (func.upper(StationORM.code).like(prefix_q), 1),
                    (func.upper(StationORM.name).like(prefix_q), 2),
                    else_=3,
                ),
                StationORM.name.asc()
            )
            .limit(limit)
        )
        
        result = await self.session.execute(stmt)
        stations = []
        for row in result.all():
            orm, lat, lon = row
            stations.append(
                Station(
                    code=orm.code,
                    name=orm.name,
                    latitude=float(lat),
                    longitude=float(lon),
                    city=orm.city,
                    state=orm.state,
                    zone=orm.zone
                )
            )
        return stations

    async def get_nearby_stations(
        self, latitude: float, longitude: float, radius_km: float
    ) -> list[tuple[Station, float]]:
        point = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        radius_meters = radius_km * 1000.0
        
        stmt = select(
            StationORM,
            func.ST_Y(func.geometry(StationORM.location)).label("lat"),
            func.ST_X(func.geometry(StationORM.location)).label("lon"),
            (func.ST_Distance(StationORM.location, point) / 1000.0).label("dist_km")
        ).where(
            ST_DWithin(StationORM.location, point, radius_meters)
        ).order_by("dist_km")
        
        result = await self.session.execute(stmt)
        nearby = []
        for row in result.all():
            orm, lat, lon, dist_km = row
            st = Station(
                code=orm.code,
                name=orm.name,
                latitude=float(lat),
                longitude=float(lon),
                city=orm.city,
                state=orm.state,
                zone=orm.zone
            )
            nearby.append((st, float(dist_km)))
        return nearby

    async def get_nearby_stations_by_code(
        self, station_code: str, radius_km: float, limit: int = 10
    ) -> Optional[list[tuple[Station, float]]]:
        clean_code = station_code.strip().upper()
        source_stmt = select(StationORM.location).where(StationORM.code == clean_code)
        source_res = await self.session.execute(source_stmt)
        source_row = source_res.first()
        if not source_row or not source_row[0]:
            return None
        
        source_location = source_row[0]
        radius_meters = radius_km * 1000.0
        
        stmt = (
            select(
                StationORM,
                func.ST_Y(func.geometry(StationORM.location)).label("lat"),
                func.ST_X(func.geometry(StationORM.location)).label("lon"),
                (func.ST_Distance(StationORM.location, source_location) / 1000.0).label("dist_km")
            )
            .where(
                StationORM.code != clean_code,
                ST_DWithin(StationORM.location, source_location, radius_meters)
            )
            .order_by("dist_km")
            .limit(limit)
        )
        
        result = await self.session.execute(stmt)
        nearby = []
        for row in result.all():
            orm, lat, lon, dist_km = row
            st = Station(
                code=orm.code,
                name=orm.name,
                latitude=float(lat),
                longitude=float(lon),
                city=orm.city,
                state=orm.state,
                zone=orm.zone
            )
            nearby.append((st, float(dist_km)))
        return nearby

    async def get_station_coverage(self, station_code: str) -> dict:
        clean_code = station_code.strip().upper()
        
        schedules_query = select(
            func.count(func.distinct(ScheduleORM.train_number))
        ).where(ScheduleORM.station_code == clean_code)
        
        origin_query = select(
            func.count(TrainORM.number)
        ).where(TrainORM.origin_code == clean_code)
        
        dest_query = select(
            func.count(TrainORM.number)
        ).where(TrainORM.destination_code == clean_code)
        
        total_trains = (await self.session.execute(schedules_query)).scalar_one() or 0
        origin_trains = (await self.session.execute(origin_query)).scalar_one() or 0
        dest_trains = (await self.session.execute(dest_query)).scalar_one() or 0
        
        has_coverage = total_trains > 0
        status_code = "VERIFIED_TIMETABLE_COVERAGE" if has_coverage else "AWAITING_COMPILED_SCHEDULES"
        note = (
            f"{total_trains} compiled train{'s call' if total_trains != 1 else ' calls'} at this station in verified timetable records."
            if has_coverage
            else "This station exists in the railway network database but currently has no compiled schedule departures in the active timetable snapshot."
        )
        
        return {
            "has_timetable_coverage": has_coverage,
            "total_compiled_trains": total_trains,
            "originating_trains_count": origin_trains,
            "terminating_trains_count": dest_trains,
            "coverage_status": status_code,
            "coverage_note": note,
        }

    async def save(self, station: Station) -> Station:
        point_wkt = f"SRID=4326;POINT({station.longitude} {station.latitude})"
        orm = await self.session.get(StationORM, station.code)
        if orm:
            orm.name = station.name
            orm.city = station.city
            orm.state = station.state
            orm.zone = station.zone
            orm.location = point_wkt
        else:
            orm = StationORM(
                code=station.code,
                name=station.name,
                city=station.city,
                state=station.state,
                zone=station.zone,
                location=point_wkt
            )
            self.session.add(orm)
        await self.session.flush()
        return station
