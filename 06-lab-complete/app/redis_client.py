import redis
from redis.exceptions import RedisError

from app.config import settings

# Chỉ tạo client tại đây; không kết nối hoặc ping lúc import.
r = redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=1,
    socket_timeout=1,
)


def redis_healthy() -> bool:
    try:
        return bool(r.ping())
    except RedisError:
        return False
