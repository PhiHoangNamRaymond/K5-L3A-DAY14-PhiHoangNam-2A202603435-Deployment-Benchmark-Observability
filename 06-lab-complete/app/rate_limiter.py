"""Atomic Redis sliding window, shared by all workers and restarts."""
import hashlib
import math
import uuid

from fastapi import HTTPException
from redis.exceptions import RedisError

from app.config import settings
from app.redis_client import r

WINDOW_MS = 60_000
SCRIPT = """
local now = redis.call('TIME')
local ms = tonumber(now[1]) * 1000 + math.floor(tonumber(now[2]) / 1000)
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ms - tonumber(ARGV[1]))
local count = redis.call('ZCARD', KEYS[1])
if count >= tonumber(ARGV[2]) then
    local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
    return {0, tonumber(oldest[2]) + tonumber(ARGV[1]) - ms}
end
redis.call('ZADD', KEYS[1], ms, ARGV[3])
redis.call('PEXPIRE', KEYS[1], ARGV[1])
return {1, tonumber(ARGV[2]) - count - 1}
"""


def check_rate_limit(key: str) -> None:
    identifier = hashlib.sha256(key.encode('utf-8')).hexdigest()
    try:
        allowed, value = r.eval(SCRIPT, 1, f'agent:rate:{identifier}',
                                WINDOW_MS, settings.rate_limit_per_minute, uuid.uuid4().hex)
    except RedisError:
        raise HTTPException(503, 'Rate limit storage unavailable') from None
    if not allowed:
        raise HTTPException(
            status_code=429, detail='Rate limit exceeded',
            headers={'Retry-After': str(max(1, math.ceil(value / 1000)))},
        )
