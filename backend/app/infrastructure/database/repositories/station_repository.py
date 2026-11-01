from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
from geoalchemy2.functions import ST_DWithin, ST_Distance, ST_SetSRID, ST_MakePoint
from app.domain.repositories.station_repository import StationRepository
from app.domain.models.station import Station
from app.infrastructure.database.models.station import StationORM

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

    async def search_by_name_or_code(self, query: str, limit: int = 10) -> list[Station]:
        q = f"%{query.strip().upper()}%"
        stmt = select(
            StationORM,
            func.ST_Y(func.geometry(StationORM.location)).label("lat"),
            func.ST_X(func.geometry(StationORM.location)).label("lon")
        ).where(
            or_(
                StationORM.code.ilike(q),
                StationORM.name.ilike(q),
                StationORM.city.ilike(q)
            )
        ).limit(limit)
        
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
