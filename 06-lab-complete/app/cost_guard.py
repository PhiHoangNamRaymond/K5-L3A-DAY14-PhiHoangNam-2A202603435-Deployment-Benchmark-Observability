"""Daily UTC budget with atomic reservations, stored in integer nano-dollars."""
import hashlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from redis.exceptions import RedisError

from app.config import settings
from app.redis_client import r

PRICE_INPUT_PER_1K = Decimal('0.00015')
PRICE_OUTPUT_PER_1K = Decimal('0.0006')
NANOS_PER_USD = 1_000_000_000
RESERVE = """
local used = tonumber(redis.call('GET', KEYS[1]) or '0')
if used + tonumber(ARGV[1]) > tonumber(ARGV[2]) then return 0 end
redis.call('INCRBY', KEYS[1], ARGV[1])
redis.call('EXPIREAT', KEYS[1], ARGV[3])
return 1
"""
ADD = """
local amount = redis.call('INCRBY', KEYS[1], ARGV[1])
redis.call('EXPIREAT', KEYS[1], ARGV[2])
return amount
"""


def estimate_tokens(text: str) -> int:
    # This lab mock does not return provider usage: label this as an estimate.
    return max(1, (len(text) + 3) // 4)


def cost_nanos(input_tokens: int, output_tokens: int) -> int:
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError('Token counts cannot be negative')
    return int((input_tokens * PRICE_INPUT_PER_1K +
                output_tokens * PRICE_OUTPUT_PER_1K) * NANOS_PER_USD / 1000)


def _period():
    now = datetime.now(timezone.utc)
    tomorrow = now.date() + timedelta(days=1)
    expires = int(datetime.combine(tomorrow, datetime.min.time(), timezone.utc).timestamp())
    identity = hashlib.sha256(settings.agent_api_key.encode('utf-8')).hexdigest()
    return f'agent:budget:{identity}:{now:%Y-%m-%d}', expires


def _limit() -> int:
    return int(Decimal(str(settings.daily_budget_usd)) * NANOS_PER_USD)


def check_budget() -> None:
    key, _ = _period()
    try:
        used = int(r.get(key) or 0)
    except RedisError:
        raise HTTPException(503, 'Budget storage unavailable') from None
    if used >= _limit():
        raise HTTPException(status_code=402, detail='Daily budget exhausted')


def reserve_cost(input_tokens: int, max_output_tokens: int) -> tuple:
    key, expires = _period()
    held = cost_nanos(input_tokens, max_output_tokens)
    try:
        accepted = r.eval(RESERVE, 1, key, held, _limit(), expires)
    except RedisError:
        raise HTTPException(503, 'Budget storage unavailable') from None
    if not accepted:
        raise HTTPException(status_code=402, detail='Insufficient daily budget')
    return key, expires, held


def record_cost(input_tokens: int, output_tokens: int, reservation=None) -> float:
    actual = cost_nanos(input_tokens, output_tokens)
    if reservation is None:
        key, expires = _period()
        difference = actual
    else:
        key, expires, held = reservation
        difference = actual - held
    try:
        r.eval(ADD, 1, key, difference, expires)
    except RedisError:
        # Keep the conservative reservation when settlement cannot reach Redis.
        raise HTTPException(503, 'Budget settlement unavailable') from None
    return actual / NANOS_PER_USD


def release_cost(reservation) -> None:
    key, expires, held = reservation
    try:
        r.eval(ADD, 1, key, -held, expires)
    except RedisError:
        # Do not discard an existing reservation if Redis is unavailable.
        pass
