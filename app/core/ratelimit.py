"""Pembatas laju sederhana berbasis Redis. Jika Redis mati: fail-open (tidak memblokir pengguna)."""
import logging

from fastapi import Request
from redis.asyncio import Redis
from redis.exceptions import RedisError

log = logging.getLogger("stockfolio.ratelimit")


def client_ip(request: Request) -> str:
    # Di belakang reverse proxy, jalankan uvicorn dengan --proxy-headers agar ini berisi IP asli.
    return request.client.host if request.client else "unknown"


async def is_blocked(redis: Redis, key: str, limit: int) -> bool:
    try:
        raw = await redis.get(key)
    except RedisError:
        log.warning("Redis tidak tersedia, pembatas laju dilewati")
        return False
    return raw is not None and int(raw) >= limit


async def add_hit(redis: Redis, key: str, window_seconds: int) -> int:
    """Tambah hitungan. SET NX EX menjamin kunci selalu punya TTL (tidak ada kunci abadi)."""
    try:
        await redis.set(key, 0, nx=True, ex=window_seconds)
        return int(await redis.incr(key))
    except RedisError:
        log.warning("Redis tidak tersedia, pembatas laju dilewati")
        return 0


async def clear(redis: Redis, key: str) -> None:
    try:
        await redis.delete(key)
    except RedisError:
        pass
