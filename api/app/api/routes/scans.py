"""Scan API router for image upload, candidate verification, and confirmation per PRD Section 11.4."""

import uuid

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models.auth import User
from app.schemas.scan import (
    ScanConfirmRequest,
    ScanConfirmResponse,
    ScanSessionResponse,
)
from app.services.scan import (
    confirm_scan_session,
    create_scan_session,
    delete_scan_session,
    get_scan_session,
)

router = APIRouter(prefix="/scans", tags=["Scans"])


@router.post(
    "",
    response_model=ScanSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload fridge photo for AI ingredient detection",
)
async def upload_scan_image(
    image: UploadFile = File(..., description="Fridge or pantry photograph (JPEG, PNG, WEBP, HEIC <= 8MB)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScanSessionResponse:
    """Upload an image of a fridge or pantry. Strips EXIF, calls Groq Vision,

    normalizes candidate ingredients, and returns candidates for verification.
    """
    file_bytes = await image.read()
    return await create_scan_session(
        db=db,
        user=current_user,
        file_bytes=file_bytes,
        filename=image.filename,
    )


@router.get(
    "/{scan_id}",
    response_model=ScanSessionResponse,
    summary="Retrieve scan session candidates",
)
def get_scan(
    scan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScanSessionResponse:
    """Retrieve scan session details and detected candidates (owner only)."""
    return get_scan_session(
        db=db,
        user=current_user,
        scan_id=scan_id,
    )


@router.post(
    "/{scan_id}/confirm",
    response_model=ScanConfirmResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Confirm candidates and add to inventory",
)
def confirm_scan(
    scan_id: uuid.UUID,
    confirm_req: ScanConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScanConfirmResponse:
    """Atomically confirm candidates, validate storage & canonical IDs,

    and write items to inventory with calculated freshness.
    """
    return confirm_scan_session(
        db=db,
        user=current_user,
        scan_id=scan_id,
        confirm_req=confirm_req,
    )


@router.delete(
    "/{scan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Discard scan session and delete image",
)
def delete_scan(
    scan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Discard a scan session and immediately delete the stored image file."""
    delete_scan_session(
        db=db,
        user=current_user,
        scan_id=scan_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
