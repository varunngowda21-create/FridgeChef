"""Unit tests for Groq Vision client, validation, repair retry, and telemetry

per PRD Section 7.2, 7.5, 9.1, 9.2, 9.3, and FR-029.
"""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from groq import RateLimitError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.db.models.analytics import LLMCall
from app.db.models.auth import User
from app.llm.client import check_groq_models_readiness, execute_groq_call_with_retries
from app.llm.vision import call_groq_vision


def _mock_chat_completion(content_json: dict | str, prompt_tokens: int | None = 150, comp_tokens: int | None = 80):
    """Helper to mock Groq chat completion response."""
    content_str = json.dumps(content_json) if isinstance(content_json, dict) else content_json

    usage_mock = None
    if prompt_tokens is not None and comp_tokens is not None:
        usage_mock = MagicMock(prompt_tokens=prompt_tokens, completion_tokens=comp_tokens)

    message_mock = MagicMock(content=content_str)
    choice_mock = MagicMock(message=message_mock)
    response_mock = MagicMock(choices=[choice_mock], usage=usage_mock)
    return response_mock


def _get_or_create_test_user(db: Session) -> User:
    """Helper to create a test user in DB to satisfy Foreign Key on llm_calls.user_id."""
    email = f"vision_test_{uuid.uuid4().hex[:8]}@example.com"
    user = User(
        email=email,
        password_hash="test_hash_bcrypt",
        display_name="Vision Tester",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.mark.asyncio
async def test_groq_vision_success(db_session):
    """Verify successful vision detection returns structured items and logs telemetry."""
    user = _get_or_create_test_user(db_session)
    valid_payload = {
        "items": [
            {
                "name": "Tomato",
                "quantity": 4,
                "unit": "piece",
                "storage_guess": "FRIDGE",
                "confidence": "HIGH",
                "visible_note": "three red, one green",
            },
            {
                "name": "Milk",
                "quantity": 1,
                "unit": "bottle",
                "storage_guess": "FRIDGE",
                "confidence": "HIGH",
                "visible_note": "sealed bottle",
            },
        ],
        "image_quality": "GOOD",
        "image_quality_note": None,
    }

    mock_resp = _mock_chat_completion(valid_payload, prompt_tokens=200, comp_tokens=90)

    with patch("app.llm.vision.get_groq_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
        mock_get_client.return_value = mock_client

        result = await call_groq_vision(
            image_bytes=b"fake_jpeg",
            db=db_session,
            user_id=user.id,
        )

        assert len(result.items) == 2
        assert result.items[0].name == "Tomato"
        assert result.items[0].quantity == 4
        assert result.items[0].unit == "piece"
        assert result.items[0].confidence == "HIGH"
        assert result.image_quality == "GOOD"

        # Verify llm_calls record in database
        call_log = (
            db_session.query(LLMCall)
            .filter(LLMCall.user_id == user.id)
            .order_by(LLMCall.created_at.desc())
            .first()
        )
        assert call_log is not None
        assert call_log.purpose == "VISION"
        assert call_log.status == "OK"
        assert call_log.prompt_tokens == 200
        assert call_log.completion_tokens == 90
        assert call_log.latency_ms >= 0


@pytest.mark.asyncio
async def test_groq_vision_missing_token_usage_safe(db_session):
    """Verify missing usage information from provider is safely recorded as None without fabricating."""
    user = _get_or_create_test_user(db_session)
    valid_payload = {
        "items": [{"name": "Potato", "quantity": 5, "unit": "piece", "storage_guess": "PANTRY", "confidence": "MEDIUM"}],
        "image_quality": "GOOD",
        "image_quality_note": None,
    }

    mock_resp = _mock_chat_completion(valid_payload, prompt_tokens=None, comp_tokens=None)

    with patch("app.llm.vision.get_groq_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
        mock_get_client.return_value = mock_client

        result = await call_groq_vision(
            image_bytes=b"fake_jpeg",
            db=db_session,
            user_id=user.id,
        )

        assert len(result.items) == 1
        call_log = (
            db_session.query(LLMCall)
            .filter(LLMCall.user_id == user.id)
            .order_by(LLMCall.created_at.desc())
            .first()
        )
        assert call_log is not None
        assert call_log.status == "OK"
        assert call_log.prompt_tokens is None
        assert call_log.completion_tokens is None


@pytest.mark.asyncio
async def test_groq_vision_repair_retry_on_schema_error(db_session):
    """Verify that a schema validation error triggers a single repair retry per PRD Section 9.3."""
    user = _get_or_create_test_user(db_session)
    invalid_payload = "Not valid JSON output at all"
    valid_payload = {
        "items": [{"name": "Carrot", "quantity": 3, "unit": "piece", "storage_guess": "FRIDGE", "confidence": "HIGH"}],
        "image_quality": "GOOD",
        "image_quality_note": None,
    }

    mock_resp_fail = _mock_chat_completion(invalid_payload)
    mock_resp_success = _mock_chat_completion(valid_payload)

    with patch("app.llm.vision.get_groq_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=[mock_resp_fail, mock_resp_success])
        mock_get_client.return_value = mock_client

        result = await call_groq_vision(
            image_bytes=b"fake_jpeg",
            db=db_session,
            user_id=user.id,
        )

        assert len(result.items) == 1
        assert result.items[0].name == "Carrot"

        # Check telemetry recorded RETRIED and then OK
        calls = (
            db_session.query(LLMCall)
            .filter(LLMCall.user_id == user.id)
            .order_by(LLMCall.created_at.asc())
            .all()
        )
        assert len(calls) >= 2
        statuses = [c.status for c in calls]
        assert "RETRIED" in statuses
        assert "OK" in statuses


@pytest.mark.asyncio
async def test_groq_vision_repair_failure_raises_502(db_session):
    """Verify that persistent invalid output after repair returns HTTP 502 VISION_UNAVAILABLE (FR-029)."""
    user = _get_or_create_test_user(db_session)
    invalid_payload = "Corrupted JSON output"
    mock_resp_fail = _mock_chat_completion(invalid_payload)

    with patch("app.llm.vision.get_groq_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp_fail)
        mock_get_client.return_value = mock_client

        with pytest.raises(AppError) as exc_info:
            await call_groq_vision(
                image_bytes=b"fake_jpeg",
                db=db_session,
                user_id=user.id,
            )

        assert exc_info.value.status_code == 502
        assert exc_info.value.code == "VISION_UNAVAILABLE"


@pytest.mark.asyncio
async def test_groq_vision_network_retries_and_failure(db_session):
    """Verify exponential backoff on network errors and HTTP 502 fallback on persistent failure."""
    user = _get_or_create_test_user(db_session)

    with patch("app.llm.vision.get_groq_client") as mock_get_client:
        mock_client = AsyncMock()
        # Mock repeated RateLimitError
        mock_client.chat.completions.create = AsyncMock(
            side_effect=RateLimitError("Rate limit exceeded", response=MagicMock(status_code=429), body=None)
        )
        mock_get_client.return_value = mock_client

        with pytest.raises(AppError) as exc_info:
            await call_groq_vision(
                image_bytes=b"fake_jpeg",
                db=db_session,
                user_id=user.id,
            )

        assert exc_info.value.status_code == 502
        assert exc_info.value.code == "VISION_UNAVAILABLE"


@pytest.mark.asyncio
async def test_groq_vision_item_capping_and_empty_name():
    """Verify output with > 60 items is capped at 60 and empty names are discarded."""
    items_data = [{"name": f"Item {i}", "quantity": 1, "unit": "piece"} for i in range(70)]
    items_data.append({"name": "   ", "quantity": 2, "unit": "piece"})  # Empty name

    payload = {
        "items": items_data,
        "image_quality": "GOOD",
        "image_quality_note": None,
    }

    from app.llm.vision import _clean_and_validate_vision_output
    result = _clean_and_validate_vision_output(payload)

    assert len(result.items) == 60
    assert all(item.name.strip() != "" for item in result.items)


@pytest.mark.asyncio
async def test_check_groq_models_readiness():
    """Verify Groq models readiness check (NFR-042)."""
    settings = Settings(
        GROQ_API_KEY="gsk_test_mock_key",
        DATABASE_URL="postgresql://user:pass@localhost:5432/db",
        JWT_SECRET="test_jwt_secret_32_characters_long",
        GROQ_VISION_MODEL="meta-llama/llama-4-scout-17b-16e-instruct",
        GROQ_TEXT_MODEL="llama-3.3-70b-versatile",
    )

    with patch("app.llm.client.get_groq_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.models.list = AsyncMock(
            return_value=MagicMock(
                data=[
                    MagicMock(id="meta-llama/llama-4-scout-17b-16e-instruct"),
                    MagicMock(id="llama-3.3-70b-versatile"),
                ]
            )
        )
        mock_get_client.return_value = mock_client

        ready, err = await check_groq_models_readiness(settings)
        assert ready is True
        assert err is None

        # Verify cache branch (< 3600s)
        ready_cached, _ = await check_groq_models_readiness(settings)
        assert ready_cached is True

        # Verify missing model branch
        mock_client.models.list = AsyncMock(
            return_value=MagicMock(data=[MagicMock(id="other-model")])
        )
        from app.llm.client import _models_cache
        _models_cache["timestamp"] = 0.0  # Invalidate cache
        ready_missing, err_msg = await check_groq_models_readiness(settings)
        assert ready_missing is False
        assert "not found" in err_msg

        # Verify exception branch
        mock_client.models.list = AsyncMock(side_effect=Exception("API connection refused"))
        _models_cache["timestamp"] = 0.0
        ready_fail, err_fail = await check_groq_models_readiness(settings)
        assert ready_fail is False
        assert "Failed to connect" in err_fail


@pytest.mark.asyncio
async def test_execute_groq_call_retries_and_errors():
    """Verify execute_groq_call_with_retries behavior on HTTP status errors."""
    from groq import APIStatusError

    # Retry on 500 then succeed
    attempts = 0

    async def flaky_call():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise APIStatusError("Server Error", response=MagicMock(status_code=500), body=None)
        return "success"

    result = await execute_groq_call_with_retries(flaky_call, max_retries=2, backoff_delays=(0.01,))
    assert result == "success"
    assert attempts == 2

    # Non-retryable 400 error immediately raises
    async def bad_request_call():
        raise APIStatusError("Bad Request", response=MagicMock(status_code=400), body=None)

    with pytest.raises(APIStatusError):
        await execute_groq_call_with_retries(bad_request_call, max_retries=2, backoff_delays=(0.01,))


def test_get_groq_client_default_settings():
    """Verify get_groq_client handles default settings."""
    from app.llm.client import get_groq_client
    client = get_groq_client()
    assert client is not None


def test_record_llm_call_db_error_resilience():
    """Verify record_llm_call logs error and does not crash when db fails."""
    from app.llm.client import record_llm_call
    mock_db = MagicMock()
    mock_db.add.side_effect = Exception("DB Disk Full")

    res = record_llm_call(
        db=mock_db,
        purpose="VISION",
        model="test-model",
        prompt_version="vision.v1",
        prompt_tokens=10,
        completion_tokens=20,
        latency_ms=100,
        status="OK",
    )
    assert res is None
