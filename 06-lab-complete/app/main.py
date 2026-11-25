import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.rate_limiter import check_rate_limit
from app.cost_guard import check_budget, reserve_cost, record_cost, release_cost, estimate_tokens
from app.redis_client import r, redis_healthy
from utils.mock_llm import ask as llm_ask, MOCK_RESPONSES


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "lvl": record.levelname,
            "event": record.getMessage(),
        }
        payload.update(getattr(record, "fields", {}))
        return json.dumps(payload, ensure_ascii=False, default=str)


handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
logger = logging.getLogger("agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "startup",
        extra={"fields": {
            "environment": settings.environment,
            "port": settings.port,
        }},
    )
    try:
        yield
    finally:
        r.close()
        logger.info("shutdown")


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


@app.middleware("http")
async def observe_requests(request: Request, call_next):
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        route = request.scope.get("route")
        logger.info(
            "http_request",
            extra={"fields": {
                "method": request.method,
                "path": getattr(route, "path", "unmatched"),
                "status": status,
                "ms": round((time.perf_counter() - start) * 1000, 2),
            }},
        )


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "environment": settings.environment,
    }


@app.get("/ready")
def ready():
    if not redis_healthy():
        raise HTTPException(
            status_code=503,
            detail="Redis unavailable",
        )
    return {"ready": True}


@app.post("/ask")
def ask(body: AskRequest, _key: str = Depends(verify_api_key)):
    check_rate_limit(_key)
    check_budget()
    input_tokens = estimate_tokens(body.question)
    # The supplied mock chooses from these fixed strings; reserve the maximum
    # possible output before calling it, then settle the estimated actual usage.
    max_output_tokens = max(
        estimate_tokens(text)
        for responses in MOCK_RESPONSES.values() for text in responses
    )
    reservation = reserve_cost(input_tokens, max_output_tokens)
    try:
        answer = llm_ask(body.question)
    except Exception:
        release_cost(reservation)
        logger.error("llm_error")
        raise HTTPException(503, "LLM upstream unavailable") from None
    output_tokens = estimate_tokens(answer)
    cost = record_cost(input_tokens, output_tokens, reservation=reservation)
    logger.info("llm_usage", extra={"fields": {
        "input_tokens": input_tokens, "output_tokens": output_tokens,
        "cost_usd": cost, "usage_source": "estimated_mock",
    }})
    return {"question": body.question, "answer": answer,
            "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens,
                      "cost_usd": cost, "source": "estimated_mock"}}
