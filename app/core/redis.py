from redis.asyncio import Redis

from app.core.config import settings

redis_client = Redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_timeout=3,
    socket_connect_timeout=3,
)


async def get_redis() -> Redis:
    return redis_client
