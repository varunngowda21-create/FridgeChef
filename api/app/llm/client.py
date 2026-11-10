"""Groq API client wrapper with retries, timeout, and observability."""

import asyncio
import logging
import time
import uuid
from typing import Any

from groq import APIConnectionError, APIStatusError, AsyncGroq, RateLimitError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models.analytics import LLMCall

logger = logging.getLogger("fridgechef.llm")

# Cached model status: (timestamp, is_ready, error_msg)
_models_cache: dict[str, Any] = {"timestamp": 0.0, "ready": False, "error": None}


def get_groq_client(settings: Settings | None = None) -> AsyncGroq:
    """Instantiate and return an AsyncGroq client."""
    if settings is None:
        from app.core.config import Settings
        settings = Settings()  # type: ignore[call-arg]

    return AsyncGroq(
        api_key=settings.GROQ_API_KEY,
        timeout=float(settings.GROQ_TIMEOUT_SECONDS),
    )


async def execute_groq_call_with_retries(
    call_coro_fn: Any,
    max_retries: int = 2,
    backoff_delays: tuple[float, ...] = (1.0, 3.0),
) -> Any:
    """Execute an async Groq SDK call with exponential backoff retries.

    Retries on HTTP 429, 500, 502, 503, 504, and network/connection errors
    per PRD Section 7.2 (NFR-010).
    """
    attempt = 0
    while True:
        try:
            return await call_coro_fn()
        except (RateLimitError, APIConnectionError) as exc:
            attempt += 1
            if attempt > max_retries:
                logger.error(f"Groq call failed after {attempt} attempts: {exc}")
                raise
            delay = backoff_delays[min(attempt - 1, len(backoff_delays) - 1)]
            logger.warning(
                f"Groq retryable error ({type(exc).__name__}): attempt {attempt}/{max_retries}. Backoff {delay}s."
            )
            await asyncio.sleep(delay)
        except APIStatusError as exc:
            status_code = getattr(exc, "status_code", 500)
            if status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                attempt += 1
                delay = backoff_delays[min(attempt - 1, len(backoff_delays) - 1)]
                logger.warning(
                    f"Groq HTTP {status_code}: attempt {attempt}/{max_retries}. Backoff {delay}s."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"Groq API error HTTP {status_code}: {exc}")
                raise
        except Exception as exc:
            logger.error(f"Unexpected Groq call exception: {exc}")
            raise


def record_llm_call(
    db: Session,
    purpose: str,
    model: str,
    prompt_version: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    latency_ms: int,
    status: str,
    user_id: uuid.UUID | None = None,
    error_code: str | None = None,
) -> LLMCall:
    """Record LLM call metrics into the llm_calls database table for observability (NFR-041).

    Never fabricates missing token usage.
    """
    try:
        call_record = LLMCall(
            user_id=user_id,
            purpose=purpose,
            model=model,
            prompt_version=prompt_version,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            status=status,
            error_code=error_code,
        )
        db.add(call_record)
        db.flush()
        return call_record
    except Exception as exc:
        logger.error(f"Failed to record LLM call in database: {exc}")
        # Never crash application flow solely due to telemetry failure
        return None  # type: ignore[return-value]


async def check_groq_models_readiness(settings: Settings) -> tuple[bool, str | None]:
    """Check Groq API availability and verify configured model IDs exist (NFR-042).

    Caches check result for 1 hour (3600s).
    """
    now = time.time()
    if _models_cache["ready"] and (now - _models_cache["timestamp"]) < 3600:
        return True, None

    try:
        client = get_groq_client(settings)
        models_response = await client.models.list()
        available_ids = {m.id for m in models_response.data}

        # Check configured vision and text models
        missing = []
        if settings.GROQ_VISION_MODEL not in available_ids:
            missing.append(settings.GROQ_VISION_MODEL)
        if settings.GROQ_TEXT_MODEL not in available_ids:
            missing.append(settings.GROQ_TEXT_MODEL)

        if missing:
            msg = f"Configured Groq models not found in model list: {', '.join(missing)}"
            logger.warning(msg)
            _models_cache["timestamp"] = now
            _models_cache["ready"] = False
            _models_cache["error"] = msg
            return False, msg

        _models_cache["timestamp"] = now
        _models_cache["ready"] = True
        _models_cache["error"] = None
        return True, None
    except Exception as exc:
        msg = f"Failed to connect to Groq models endpoint: {exc}"
        logger.warning(msg)
        _models_cache["timestamp"] = now
        _models_cache["ready"] = False
        _models_cache["error"] = msg
        return False, msg
