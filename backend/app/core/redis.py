import redis.asyncio as redis
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

redis_client = redis.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True
)

async def check_redis_health() -> bool:
    try:
        pong = await redis_client.ping()
        return pong is True
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return False
