from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from app.core.config import settings
from app.core.db import check_database_health
from app.core.redis import check_redis_health

router = APIRouter(prefix="/health", tags=["Health"])

class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str

class ReadinessServices(BaseModel):
    database: bool
    redis: bool

class ReadinessResponse(BaseModel):
    status: str
    services: ReadinessServices

@router.get("", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="ok",
        version=settings.VERSION,
        environment=settings.ENVIRONMENT
    )

@router.get("/ready", response_model=ReadinessResponse)
async def readiness_check():
    db_healthy = await check_database_health()
    redis_healthy = await check_redis_health()
    
    is_ready = db_healthy and redis_healthy
    status_str = "ready" if is_ready else "unhealthy"
    
    response = ReadinessResponse(
        status=status_str,
        services=ReadinessServices(
            database=db_healthy,
            redis=redis_healthy
        )
    )
    
    if not is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=response.model_dump()
        )
        
    return response
