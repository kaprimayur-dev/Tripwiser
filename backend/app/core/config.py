from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "TripWiser API"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    
    # Database & Redis Settings
    DATABASE_URL: str = "postgresql+asyncpg://tripwiser:tripwiser@localhost:5432/tripwiser_db"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Provider Settings
    AVAILABILITY_PROVIDER: str = "mock"
    CHART_VACANCY_PROVIDER: str = "mock"
    
    # Search Constraints
    MIN_TRANSFER_MINUTES: int = 45
    MAX_LAYOVER_MINUTES: int = 240
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
