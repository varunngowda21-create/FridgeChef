"""Scan session service for fridge image processing, candidate normalization,

and transactional verification per PRD Section 6.3, 7.3, 8.4, and 11.4.
"""

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.core.ratelimit import scan_rate_limiter
from app.db.models.analytics import RecommendationCache
from app.db.models.auth import User
from app.db.models.catalogue import Ingredient
from app.db.models.inventory import InventoryItem, ScanSession
from app.llm.vision import call_groq_vision
from app.media.image_pipeline import (
    delete_image_file,
    save_processed_image,
    validate_and_process_image,
)
from app.schemas.inventory import InventoryItemResponse
from app.schemas.scan import (
    ScanCandidate,
    ScanConfirmItem,
    ScanConfirmRequest,
    ScanConfirmResponse,
    ScanSessionResponse,
)
from app.services.freshness import get_freshness_for_item
from app.services.inventory import to_inventory_item_response
from app.services.normalise import alias_matcher
from app.services.units import normalize_unit

logger = logging.getLogger("fridgechef.scan")


async def create_scan_session(
    db: Session,
    user: User,
    file_bytes: bytes,
    filename: str | None = None,
    settings: Settings | None = None,
) -> ScanSessionResponse:
    """Ingest image, validate, strip EXIF, call Groq Vision, normalize candidates,

    and persist a scan session with 30m TTL.
    """
    if settings is None:
        from app.core.config import Settings
        settings = Settings()  # type: ignore[call-arg]

    # 1. Enforce scan rate limit: 20 scans per day per user (NFR-022, PRD 11.4)
    scan_rate_limiter.check_and_record(str(user.id))

    # 2. Process image (validates mime, size <= 8MB, EXIF stripped, max 1600px, JPEG q85 <= 4MB)
    processed_image = validate_and_process_image(
        file_bytes=file_bytes,
        max_upload_mb=settings.MAX_UPLOAD_MB,
    )

    scan_id = uuid.uuid4()

    # 3. Save resized copy outside web root with safe UUID filename
    saved_path = save_processed_image(
        scan_id=scan_id,
        image_bytes=processed_image.data,
        upload_dir=settings.UPLOAD_DIR,
    )

    # 4. Call Groq Vision
    try:
        vision_result = await call_groq_vision(
            image_bytes=processed_image.data,
            db=db,
            user_id=user.id,
            settings=settings,
        )
    except Exception:
        # Cleanup temporary image file if vision processing fails
        delete_image_file(saved_path)
        raise

    # 5. Normalize items using alias matcher
    candidates: list[ScanCandidate] = []
    for item in vision_result.items:
        candidate_id = uuid.uuid4()
        canonical_id, canonical_name = alias_matcher.match(item.name)

        display_name = canonical_name if canonical_name else item.name
        confidence = (item.confidence or "MEDIUM").upper()

        # Low confidence or unmapped items need review per PRD Section 5.2 & FR-025
        needs_review = (canonical_id is None) or (confidence == "LOW")

        storage_guess = item.storage_guess.upper() if item.storage_guess else "UNKNOWN"
        if storage_guess not in {"FRIDGE", "FREEZER", "PANTRY", "COUNTER", "UNKNOWN"}:
            storage_guess = "UNKNOWN"

        unit = normalize_unit(item.unit) if item.unit else "unknown"

        candidates.append(
            ScanCandidate(
                candidate_id=candidate_id,
                name=display_name,
                canonical_id=canonical_id,
                quantity=item.quantity,
                unit=unit,
                storage_guess=storage_guess,
                confidence=confidence,
                needs_review=needs_review,
                visible_note=item.visible_note,
            )
        )

    # 6. Save ScanSession in database (30m expiry per FR-026)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
    session_model = ScanSession(
        id=scan_id,
        user_id=user.id,
        status="PENDING_VERIFY",
        image_path=saved_path,
        candidates=[c.model_dump(mode="json") for c in candidates],
        image_quality=vision_result.image_quality,
        image_quality_note=vision_result.image_quality_note,
        expires_at=expires_at,
    )
    db.add(session_model)
    db.commit()
    db.refresh(session_model)

    return ScanSessionResponse(
        scan_id=session_model.id,
        status=session_model.status,
        expires_at=session_model.expires_at,
        image_quality=session_model.image_quality or "GOOD",
        image_quality_note=session_model.image_quality_note,
        candidates=candidates,
    )


def get_scan_session(
    db: Session,
    user: User,
    scan_id: uuid.UUID,
) -> ScanSessionResponse:
    """Retrieve scan session candidates for authenticated owner."""
    session = db.query(ScanSession).filter(ScanSession.id == scan_id).first()
    if not session or session.user_id != user.id:
        raise AppError(
            code="SCAN_SESSION_NOT_FOUND",
            message="Scan session not found.",
            status_code=404,
        )

    now = datetime.now(timezone.utc)
    if session.status == "PENDING_VERIFY" and session.expires_at < now:
        session.status = "EXPIRED"
        if session.image_path:
            delete_image_file(session.image_path)
            session.image_path = None
        db.commit()
        db.refresh(session)

    candidates = [ScanCandidate.model_validate(c) for c in session.candidates]

    return ScanSessionResponse(
        scan_id=session.id,
        status=session.status,
        expires_at=session.expires_at,
        image_quality=session.image_quality or "GOOD",
        image_quality_note=session.image_quality_note,
        candidates=candidates,
    )


def confirm_scan_session(
    db: Session,
    user: User,
    scan_id: uuid.UUID,
    confirm_req: ScanConfirmRequest,
) -> ScanConfirmResponse:
    """Validate and atomically confirm scan candidates into inventory items.

    Enforces:
    - Ownership verification
    - Session active and not expired
    - Canonical ID required for each item (HTTP 422 CANONICAL_ID_REQUIRED)
    - Storage applicability check (HTTP 422 STORAGE_NOT_APPLICABLE)
    - Single atomic database transaction (rollback on any failure)
    - Image deletion immediately upon confirmation
    - Recommendation cache invalidation
    """
    session = db.query(ScanSession).filter(ScanSession.id == scan_id).first()
    if not session or session.user_id != user.id:
        raise AppError(
            code="SCAN_SESSION_NOT_FOUND",
            message="Scan session not found.",
            status_code=404,
        )

    now = datetime.now(timezone.utc)
    if session.expires_at < now or session.status == "EXPIRED":
        session.status = "EXPIRED"
        if session.image_path:
            delete_image_file(session.image_path)
            session.image_path = None
        db.commit()
        raise AppError(
            code="SCAN_SESSION_EXPIRED",
            message="Scan session has expired.",
            status_code=400,
        )

    if session.status != "PENDING_VERIFY":
        raise AppError(
            code="SCAN_SESSION_ALREADY_PROCESSED",
            message=f"Scan session status is {session.status}.",
            status_code=400,
        )

    # Pre-validation pass: validate ALL items before any persistence to ensure transactional atomicity
    validated_items_data: list[tuple[ScanConfirmItem, str, Any]] = []
    today = date.today()

    for item in confirm_req.items:
        # Check canonical ID
        if not item.canonical_id or not item.canonical_id.strip():
            raise AppError(
                code="CANONICAL_ID_REQUIRED",
                message="Item requires a valid canonical ingredient ID.",
                status_code=422,
            )

        canonical_id = item.canonical_id.strip().lower()
        ingredient = db.query(Ingredient).filter(Ingredient.id == canonical_id).first()
        if not ingredient:
            raise AppError(
                code="INGREDIENT_NOT_FOUND",
                message=f"Canonical ingredient '{canonical_id}' does not exist.",
                status_code=404,
            )

        # Validate storage applicability and calculate freshness
        freshness = get_freshness_for_item(
            db=db,
            ingredient_id=canonical_id,
            storage=item.storage,
            added_on=today,
            opened_on=item.opened_on,
            today=today,
        )

        unit = normalize_unit(item.unit)
        validated_items_data.append((item, unit, freshness))

    # Transactional execution
    created_items: list[InventoryItemResponse] = []
    confirmed_candidate_ids: set[str] = set()

    try:
        for item, unit, freshness in validated_items_data:
            inv_item = InventoryItem(
                user_id=user.id,
                ingredient_id=item.canonical_id.strip().lower(),  # type: ignore[union-attr]
                display_name=item.name.strip(),
                quantity=item.quantity,
                unit=unit,
                storage=item.storage.strip().upper(),
                added_on=today,
                opened_on=item.opened_on,
                shelf_life_days_estimate=freshness.base_life,
                expires_on=freshness.expires_on,
                archived_at=None,
            )
            db.add(inv_item)
            db.flush()
            db.refresh(inv_item)

            created_items.append(to_inventory_item_response(inv_item, freshness))

            if item.candidate_id:
                confirmed_candidate_ids.add(str(item.candidate_id))

        # Calculate skipped candidates
        skipped_ids: list[str] = []
        for candidate_dict in session.candidates:
            c_id = str(candidate_dict.get("candidate_id"))
            if c_id not in confirmed_candidate_ids:
                skipped_ids.append(c_id)

        # Mark session CONFIRMED
        session.status = "CONFIRMED"

        # Delete image file from disk immediately per PRD Section 6.3 FR-028 & NFR-031
        if session.image_path:
            delete_image_file(session.image_path)
            session.image_path = None

        # Invalidate recommendation cache (PRD FR-046)
        db.query(RecommendationCache).filter(RecommendationCache.user_id == user.id).delete()

        db.commit()

        return ScanConfirmResponse(
            created=created_items,
            skipped=skipped_ids,
        )

    except Exception:
        db.rollback()
        raise


def delete_scan_session(
    db: Session,
    user: User,
    scan_id: uuid.UUID,
) -> None:
    """Discard a scan session and delete its image immediately per PRD Section 11.4."""
    session = db.query(ScanSession).filter(ScanSession.id == scan_id).first()
    if not session or session.user_id != user.id:
        raise AppError(
            code="SCAN_SESSION_NOT_FOUND",
            message="Scan session not found.",
            status_code=404,
        )

    if session.image_path:
        delete_image_file(session.image_path)
        session.image_path = None

    db.delete(session)
    db.commit()


def cleanup_expired_scans(db: Session, max_age_hours: int = 24) -> int:
    """Background task to delete image files of expired scan sessions (PRD FR-028)."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=max_age_hours)

    sessions = (
        db.query(ScanSession)
        .filter(
            ((ScanSession.expires_at < now) & (ScanSession.status == "PENDING_VERIFY"))
            | (ScanSession.created_at < cutoff)
        )
        .all()
    )

    cleaned_count = 0
    for s in sessions:
        if s.image_path:
            delete_image_file(s.image_path)
            s.image_path = None
        if s.status == "PENDING_VERIFY":
            s.status = "EXPIRED"
        cleaned_count += 1

    db.commit()
    return cleaned_count
