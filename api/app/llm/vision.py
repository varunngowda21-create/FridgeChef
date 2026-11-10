"""Groq Vision service for ingredient detection from photos."""

import base64
import json
import logging
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.llm.client import execute_groq_call_with_retries, get_groq_client, record_llm_call
from app.llm.prompts.vision_v1 import PROMPT_VERSION, REPAIR_PROMPT, SYSTEM_PROMPT, USER_INSTRUCTION

logger = logging.getLogger("fridgechef.vision")

VALID_UNITS = {"piece", "bunch", "packet", "container", "bottle", "g", "ml", "unknown"}
VALID_STORAGES = {"FRIDGE", "FREEZER", "PANTRY", "COUNTER", "UNKNOWN"}
VALID_CONFIDENCES = {"HIGH", "MEDIUM", "LOW"}


class VisionItem(BaseModel):
    name: str
    quantity: float | None = None
    unit: str = "unknown"
    storage_guess: str = "UNKNOWN"
    confidence: str = "MEDIUM"
    visible_note: str | None = None


class VisionResponse(BaseModel):
    items: list[VisionItem] = Field(default_factory=list)
    image_quality: str = "GOOD"
    image_quality_note: str | None = None


def _clean_and_validate_vision_output(raw_data: dict[str, Any]) -> VisionResponse:
    """Validate and normalize parsed JSON against the vision schema.

    Enforces:
    - Valid schema
    - Cap items at 60
    - Discard items with empty names
    - Sanitize enums
    - visible_note max 80 chars
    """
    parsed = VisionResponse.model_validate(raw_data)

    sanitized_items: list[VisionItem] = []
    for item in parsed.items:
        clean_name = item.name.strip() if item.name else ""
        if not clean_name:
            continue

        unit = item.unit.lower() if item.unit else "unknown"
        if unit not in VALID_UNITS:
            unit = "unknown"

        storage = (item.storage_guess or "UNKNOWN").upper()
        if storage not in VALID_STORAGES:
            storage = "UNKNOWN"

        confidence = (item.confidence or "MEDIUM").upper()
        if confidence not in VALID_CONFIDENCES:
            confidence = "MEDIUM"

        note = item.visible_note.strip() if item.visible_note else None
        if note and len(note) > 80:
            note = note[:80]

        qty = item.quantity
        if qty is not None and qty < 0:
            qty = None

        sanitized_items.append(
            VisionItem(
                name=clean_name,
                quantity=qty,
                unit=unit,
                storage_guess=storage,
                confidence=confidence,
                visible_note=note,
            )
        )

        if len(sanitized_items) >= 60:
            break

    quality = (parsed.image_quality or "GOOD").upper()
    if quality not in {"GOOD", "POOR"}:
        quality = "GOOD"

    return VisionResponse(
        items=sanitized_items,
        image_quality=quality,
        image_quality_note=parsed.image_quality_note,
    )


async def call_groq_vision(
    image_bytes: bytes,
    db: Session,
    user_id: uuid.UUID | None = None,
    settings: Settings | None = None,
) -> VisionResponse:
    """Call Groq Vision API with the processed JPEG image, validate schema,

    and retry with a repair prompt on validation error per PRD Section 9.3 & FR-029.
    """
    if settings is None:
        from app.core.config import Settings
        settings = Settings()  # type: ignore[call-arg]

    client = get_groq_client(settings)
    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:image/jpeg;base64,{b64_image}"

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": USER_INSTRUCTION},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        },
    ]

    model_name = settings.GROQ_VISION_MODEL
    start_time = time.perf_counter()

    try:
        # First attempt with retries for network/rate limits
        async def _call_attempt():
            return await client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.1,
                max_completion_tokens=900,
                response_format={"type": "json_object"},
            )

        response = await execute_groq_call_with_retries(
            _call_attempt,
            max_retries=settings.GROQ_MAX_RETRIES,
        )

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        content = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
        completion_tokens = getattr(usage, "completion_tokens", None) if usage else None

        # Parse and validate schema
        try:
            parsed_json = json.loads(content)
            validated_response = _clean_and_validate_vision_output(parsed_json)

            # Record success telemetry
            record_llm_call(
                db=db,
                purpose="VISION",
                model=model_name,
                prompt_version=PROMPT_VERSION,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                status="OK",
                user_id=user_id,
            )
            return validated_response

        except (json.JSONDecodeError, ValidationError) as parse_exc:
            logger.warning(
                f"Vision output failed schema validation ({parse_exc}). Attempting repair retry per PRD Section 9.3."
            )

            # Record retried telemetry
            record_llm_call(
                db=db,
                purpose="VISION",
                model=model_name,
                prompt_version=PROMPT_VERSION,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                status="RETRIED",
                user_id=user_id,
                error_code="SCHEMA_VALIDATION_ERROR",
            )

            # Single repair attempt
            repair_messages = list(messages)
            repair_messages.append({"role": "assistant", "content": content})
            repair_messages.append(
                {
                    "role": "user",
                    "content": REPAIR_PROMPT.format(error_message=str(parse_exc)),
                }
            )

            repair_start = time.perf_counter()
            async def _call_repair():
                return await client.chat.completions.create(
                    model=model_name,
                    messages=repair_messages,
                    temperature=0.1,
                    max_completion_tokens=900,
                    response_format={"type": "json_object"},
                )

            repair_response = await execute_groq_call_with_retries(
                _call_repair,
                max_retries=settings.GROQ_MAX_RETRIES,
            )
            repair_latency_ms = int((time.perf_counter() - repair_start) * 1000)
            repair_content = repair_response.choices[0].message.content or ""
            repair_usage = getattr(repair_response, "usage", None)
            rep_prompt_tokens = getattr(repair_usage, "prompt_tokens", None) if repair_usage else None
            rep_comp_tokens = getattr(repair_usage, "completion_tokens", None) if repair_usage else None

            try:
                repair_json = json.loads(repair_content)
                validated_response = _clean_and_validate_vision_output(repair_json)

                record_llm_call(
                    db=db,
                    purpose="VISION",
                    model=model_name,
                    prompt_version=PROMPT_VERSION,
                    prompt_tokens=rep_prompt_tokens,
                    completion_tokens=rep_comp_tokens,
                    latency_ms=repair_latency_ms,
                    status="OK",
                    user_id=user_id,
                )
                return validated_response
            except Exception as final_exc:
                logger.error(f"Repair attempt failed: {final_exc}")
                record_llm_call(
                    db=db,
                    purpose="VISION",
                    model=model_name,
                    prompt_version=PROMPT_VERSION,
                    prompt_tokens=rep_prompt_tokens,
                    completion_tokens=rep_comp_tokens,
                    latency_ms=repair_latency_ms,
                    status="ERROR",
                    user_id=user_id,
                    error_code="REPAIR_FAILED",
                )
                raise AppError(
                    code="VISION_UNAVAILABLE",
                    message="Vision detection is currently unavailable. You can add items manually.",
                    status_code=502,
                ) from None

    except AppError:
        raise
    except Exception as exc:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        logger.error(f"Groq vision persistent failure: {exc}", exc_info=True)
        record_llm_call(
            db=db,
            purpose="VISION",
            model=model_name,
            prompt_version=PROMPT_VERSION,
            prompt_tokens=None,
            completion_tokens=None,
            latency_ms=latency_ms,
            status="ERROR",
            user_id=user_id,
            error_code=type(exc).__name__,
        )
        raise AppError(
            code="VISION_UNAVAILABLE",
            message="Vision detection is currently unavailable. You can add items manually.",
            status_code=502,
        ) from None
