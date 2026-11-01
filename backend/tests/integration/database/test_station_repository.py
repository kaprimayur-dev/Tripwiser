import pytest
from app.core.db import check_database_health, AsyncSessionLocal
from app.domain.models.station import Station
from app.infrastructure.database.repositories.station_repository import SQLAlchemyStationRepository


@pytest.mark.asyncio
async def test_station_repository_flow():
    db_healthy = await check_database_health()
    if not db_healthy:
        pytest.skip("PostgreSQL/PostGIS database is not available in current execution environment.")

    async with AsyncSessionLocal() as session:
        try:
            repo = SQLAlchemyStationRepository(session)

            # 1. Create and Save Station
            st = Station(
                code="GWL",
                name="Gwalior Junction",
                latitude=26.2183,
                longitude=78.1828,
                city="Gwalior",
                state="Madhya Pradesh",
                zone="NCR"
            )
            saved = await repo.save(st)
            assert saved.code == "GWL"

            # 2. Retrieve by Code and Verify PostGIS Spatial Data
            retrieved = await repo.get_by_code("GWL")
            assert retrieved is not None
            assert retrieved.code == "GWL"
            assert retrieved.name == "Gwalior Junction"
            assert abs(retrieved.latitude - 26.2183) < 0.001
            assert abs(retrieved.longitude - 78.1828) < 0.001

            # 3. Test Autocomplete Search
            results = await repo.search_by_name_or_code("Gwalior")
            assert len(results) >= 1
            assert any(s.code == "GWL" for s in results)

            # 4. Test PostGIS Spatial Distance Search
            nearby = await repo.get_nearby_stations(26.20, 78.18, radius_km=50.0)
            assert len(nearby) >= 1
            matching = [s for s, dist in nearby if s.code == "GWL"]
            assert len(matching) == 1
            assert nearby[0][1] >= 0.0

        finally:
            await session.rollback()
