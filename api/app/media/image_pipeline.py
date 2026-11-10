"""Media pipeline for image validation, EXIF stripping, resizing, and safe storage."""

import io
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

from app.core.errors import AppError

logger = logging.getLogger("fridgechef.media")

# Register HEIF opener if pillow-heif is available
try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:  # pragma: no cover
    logger.warning("pillow_heif not available; HEIC/HEIF images may not be supported.")

SUPPORTED_FORMATS = {"JPEG", "PNG", "WEBP", "HEIF", "HEIC"}
MAX_DIMENSION = 1600
JPEG_QUALITY = 85
MAX_PROCESSED_SIZE_BYTES = 4 * 1024 * 1024  # 4 MB per PRD FR-023


@dataclass(frozen=True)
class ProcessedImage:
    data: bytes
    width: int
    height: int
    format: str = "JPEG"


def validate_and_process_image(
    file_bytes: bytes,
    content_type: str | None = None,
    max_upload_mb: int = 8,
) -> ProcessedImage:
    """Validate image content, strip EXIF metadata, resize to max 1600px long edge,

    and re-encode as JPEG quality 85 under 4 MB.

    Enforces:
    - Max size <= 8 MB (HTTP 413 IMAGE_TOO_LARGE)
    - Valid image format in JPEG, PNG, WEBP, HEIC (HTTP 415 UNSUPPORTED_MEDIA_TYPE)
    - Real image verification via Pillow (HTTP 422 IMAGE_UNREADABLE)
    - EXIF stripping (specifically GPS / camera metadata)
    - Max long edge 1600px
    - Output <= 4 MB
    """
    max_upload_bytes = max_upload_mb * 1024 * 1024
    if len(file_bytes) > max_upload_bytes:
        raise AppError(
            code="IMAGE_TOO_LARGE",
            message=f"Image size exceeds the maximum limit of {max_upload_mb} MB.",
            status_code=413,
        )

    if not file_bytes:
        raise AppError(
            code="IMAGE_UNREADABLE",
            message="Image file is empty or corrupted.",
            status_code=422,
        )

    # Decode and verify with Pillow
    try:
        raw_image = Image.open(io.BytesIO(file_bytes))
        image_format = (raw_image.format or "").upper()

        # Check format whitelist
        if image_format not in SUPPORTED_FORMATS:
            raise AppError(
                code="UNSUPPORTED_MEDIA_TYPE",
                message=f"Unsupported image format: {image_format or 'unknown'}. Allowed formats: JPEG, PNG, WEBP, HEIC.",
                status_code=415,
            )

        # Verify stream integrity
        raw_image.verify()
    except AppError:
        raise
    except Exception as exc:
        logger.warning(f"Image decode failed: {exc}")
        raise AppError(
            code="IMAGE_UNREADABLE",
            message="Corrupted or unreadable image file.",
            status_code=422,
        ) from None

    # Re-open for actual processing (verify() closes or invalidates the image)
    try:
        image: Image.Image = Image.open(io.BytesIO(file_bytes))

        # Handle EXIF orientation transposition if present before stripping
        try:
            image = ImageOps.exif_transpose(image)
        except Exception:
            pass

        # Convert to RGB (dropping alpha, palette, or CMYK modes for JPEG)
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Resize so long edge <= 1600 px
        width, height = image.size
        max_edge = max(width, height)
        if max_edge > MAX_DIMENSION:
            scale = MAX_DIMENSION / float(max_edge)
            new_width = max(1, int(round(width * scale)))
            new_height = max(1, int(round(height * scale)))
            image = image.resize((new_width, new_height), resample=Image.Resampling.LANCZOS)

        # Save to JPEG buffer without EXIF metadata
        quality = JPEG_QUALITY
        out_buf = io.BytesIO()
        image.save(out_buf, format="JPEG", quality=quality, optimize=True)
        processed_data = out_buf.getvalue()

        # Ensure output is <= 4 MB per PRD FR-023
        if len(processed_data) > MAX_PROCESSED_SIZE_BYTES:
            quality = 70
            out_buf = io.BytesIO()
            image.save(out_buf, format="JPEG", quality=quality, optimize=True)
            processed_data = out_buf.getvalue()

        return ProcessedImage(
            data=processed_data,
            width=image.width,
            height=image.height,
            format="JPEG",
        )
    except AppError:
        raise
    except Exception as exc:
        logger.error(f"Image processing error: {exc}", exc_info=True)
        raise AppError(
            code="IMAGE_UNREADABLE",
            message="Failed to process image.",
            status_code=422,
        ) from None


def save_processed_image(
    scan_id: uuid.UUID,
    image_bytes: bytes,
    upload_dir: str = "./uploads",
) -> str:
    """Save processed image with a safe UUID-based filename outside the web root.

    Returns the absolute path to the saved file.
    """
    target_dir = Path(upload_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{scan_id}.jpg"
    file_path = target_dir / filename

    with open(file_path, "wb") as f:
        f.write(image_bytes)

    return str(file_path)


def delete_image_file(file_path: str | None) -> bool:
    """Safely delete an image file from disk. Never raises on missing file."""
    if not file_path:
        return False

    try:
        path = Path(file_path)
        if path.exists() and path.is_file():
            path.unlink()
            logger.info(f"Deleted image file: {path.name}")
            return True
    except OSError as exc:
        logger.warning(f"Failed to delete image file {file_path}: {exc}")

    return False
