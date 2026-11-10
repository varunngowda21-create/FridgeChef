import logging
import time

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.health import HealthResponse, ReadyResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])

# 1-hour Groq health cache per PRD Section 14.1
_groq_cache: dict[str, float | str | None] = {
    "last_checked": None,
    "status": None,
}


def check_groq_availability(api_key: str) -> str:
    now = time.time()
    last = _groq_cache["last_checked"]

    # Use cached result if within 1 hour (3600 seconds)
    if (
        last is not None
        and (now - float(last)) < 3600
        and _groq_cache["status"] is not None
    ):
        return str(_groq_cache["status"])

    if not api_key or api_key.startswith("gsk_placeholder"):
        # Without a live key, mark as unconfigured
        _groq_cache["last_checked"] = now
        _groq_cache["status"] = "unconfigured"
        return "unconfigured"

    try:
        from groq import Groq

        client = Groq(api_key=api_key, timeout=5.0)
        client.models.list()
        _groq_cache["last_checked"] = now
        _groq_cache["status"] = "available"
        return "available"
    except Exception as e:
        logger.warning("Groq readiness check failed: %s", e)
        _groq_cache["last_checked"] = now
        _groq_cache["status"] = "unavailable"
        return "unavailable"


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness Probe",
    description="Returns healthy if API process is running.",
)
def get_liveness() -> HealthResponse:
    return HealthResponse(status="healthy")


@router.get(
    "/health/ready",
    response_model=ReadyResponse,
    responses={
        200: {"model": ReadyResponse},
        503: {"description": "Service Unavailable"},
    },
    summary="Readiness Probe",
    description="Verifies database connectivity and Groq API status (cached 1hr).",
)
def get_readiness(db: Session = Depends(get_db)):
    settings = get_settings()

    # 1. Database check
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error("Database readiness check failed: %s", e)
        db_status = "disconnected"

    # 2. Groq check
    groq_status = check_groq_availability(settings.GROQ_API_KEY)

    # In production or standard readiness: DB must be connected
    is_ready = (db_status == "connected")

    overall_status = "ready" if is_ready else "not_ready"
    response_payload = ReadyResponse(
        status=overall_status,
        database=db_status,
        groq=groq_status,
    )

    if not is_ready:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=response_payload.model_dump(),
        )

    return response_payload
