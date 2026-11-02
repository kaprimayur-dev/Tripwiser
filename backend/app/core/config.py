import json
from typing import List, Union
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine.url import make_url

class Settings(BaseSettings):
    PROJECT_NAME: str = "TripWiser API"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    
    # Database & Redis Settings
    DATABASE_URL: str = "postgresql+asyncpg://tripwiser:tripwiser@localhost:5432/tripwiser_db"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Allowed CORS Origins (supports list of strings or JSON-serialized array)
    BACKEND_CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    
    # Provider Settings
    AVAILABILITY_PROVIDER: str = "mock"
    CHART_VACANCY_PROVIDER: str = "mock"
    
    # Search Constraints
    MIN_TRANSFER_MINUTES: int = 30
    MAX_LAYOVER_MINUTES: int = 360

    @property
    def cors_origins_list(self) -> List[str]:
        """Parsed list of CORS origin strings."""
        if isinstance(self.BACKEND_CORS_ORIGINS, list):
            return [str(o).strip() for o in self.BACKEND_CORS_ORIGINS if str(o).strip()]
        if isinstance(self.BACKEND_CORS_ORIGINS, str):
            val = self.BACKEND_CORS_ORIGINS.strip()
            if val.startswith("[") and val.endswith("]"):
                try:
                    parsed = json.loads(val)
                    if isinstance(parsed, list):
                        return [str(o).strip() for o in parsed if str(o).strip()]
                except Exception:
                    pass
            return [x.strip() for x in val.split(",") if x.strip()]
        return ["http://localhost:3000"]

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """
        Safely normalizes DATABASE_URL for asyncpg driver:
        1. Translates 'postgres://' or 'postgresql://' to 'postgresql+asyncpg://'.
        2. Preserves SSL requirements without weakening: maps 'sslmode' parameters
           (require, verify-full, verify-ca) to asyncpg's 'ssl=require'.
        3. Preserves local Docker connection strings without alteration.
        """
        raw = self.DATABASE_URL.strip()
        if not raw:
            return raw

        try:
            url = make_url(raw)
            drivername = url.drivername
            if drivername in ("postgres", "postgresql", "postgres+asyncpg"):
                drivername = "postgresql+asyncpg"

            query = dict(url.query)
            if "sslmode" in query:
                mode = query.pop("sslmode").lower()
                if mode in ("require", "verify-ca", "verify-full", "prefer", "allow"):
                    query["ssl"] = "require"
                elif mode in ("disable", "off", "no"):
                    query["ssl"] = "disable"

            url = url.set(drivername=drivername, query=query)
            return url.render_as_string(hide_password=False)
        except Exception:
            if raw.startswith("postgres://"):
                return raw.replace("postgres://", "postgresql+asyncpg://", 1)
            elif raw.startswith("postgresql://"):
                return raw.replace("postgresql://", "postgresql+asyncpg://", 1)
            return raw
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
