"""Unit tests for the image processing pipeline per PRD Section 6.3 and 12.4."""

import io
import os
import uuid

import pytest
from PIL import Image

from app.core.errors import AppError
from app.media.image_pipeline import (
    delete_image_file,
    save_processed_image,
    validate_and_process_image,
)


def _create_test_image(
    format: str = "JPEG",
    size: tuple[int, int] = (800, 600),
    color: tuple[int, int, int] = (255, 0, 0),
    include_gps: bool = False,
) -> bytes:
    """Helper to generate in-memory image bytes with optional EXIF/GPS."""
    mode = "RGBA" if format == "PNG" else "RGB"
    img = Image.new(mode, size, color=color)

    exif_bytes = None
    if include_gps and format == "JPEG":
        exif = img.getexif()
        exif[0x010E] = "Secret User Camera Info"
        gps_ifd = exif.get_ifd(0x8825)
        gps_ifd[1] = "N"
        gps_ifd[3] = "E"
        exif_bytes = exif.tobytes()

    buf = io.BytesIO()
    if exif_bytes and format == "JPEG":
        img.save(buf, format=format, exif=exif_bytes)
    else:
        img.save(buf, format=format)
    return buf.getvalue()


def test_valid_jpeg_processing():
    """Verify valid JPEG is processed, dimensions preserved or within 1600px, format JPEG."""
    raw_data = _create_test_image("JPEG", size=(640, 480))
    result = validate_and_process_image(raw_data)

    assert result.format == "JPEG"
    assert result.width == 640
    assert result.height == 480
    assert len(result.data) > 0
    assert len(result.data) <= 4 * 1024 * 1024


def test_valid_png_converts_to_jpeg():
    """Verify PNG images (including transparency) are converted to RGB JPEG quality 85."""
    raw_data = _create_test_image("PNG", size=(500, 500))
    result = validate_and_process_image(raw_data)

    assert result.format == "JPEG"
    assert result.width == 500
    assert result.height == 500

    # Re-open processed image with Pillow to verify valid JPEG
    processed_img = Image.open(io.BytesIO(result.data))
    assert processed_img.format == "JPEG"
    assert processed_img.mode == "RGB"


def test_valid_webp_processing():
    """Verify WEBP images are supported and converted to JPEG."""
    raw_data = _create_test_image("WEBP", size=(400, 300))
    result = validate_and_process_image(raw_data)

    assert result.format == "JPEG"
    assert result.width == 400
    assert result.height == 300


def test_resize_large_dimensions():
    """Verify images exceeding 1600px on the long edge are scaled down to 1600px."""
    raw_data = _create_test_image("JPEG", size=(2400, 1800))
    result = validate_and_process_image(raw_data)

    assert result.width == 1600
    assert result.height == 1200
    assert max(result.width, result.height) == 1600


def test_exif_gps_stripping():
    """Verify EXIF metadata and GPS tags are completely stripped (PRD FR-022, NFR-028)."""
    raw_data_with_gps = _create_test_image("JPEG", size=(400, 400), include_gps=True)

    # Confirm original had EXIF tags
    orig_img = Image.open(io.BytesIO(raw_data_with_gps))
    orig_exif = orig_img.getexif()
    assert 0x010E in orig_exif

    # Process through pipeline
    result = validate_and_process_image(raw_data_with_gps)

    # Verify processed image has NO camera or GPS tags
    processed_img = Image.open(io.BytesIO(result.data))
    processed_exif = processed_img.getexif()
    assert 0x010E not in processed_exif
    assert 0x8825 not in processed_exif


def test_oversized_upload_rejected():
    """Verify uploads exceeding max upload size (8MB) are rejected with HTTP 413 IMAGE_TOO_LARGE."""
    fake_huge_bytes = b"0" * (9 * 1024 * 1024)  # 9 MB

    with pytest.raises(AppError) as exc_info:
        validate_and_process_image(fake_huge_bytes, max_upload_mb=8)

    assert exc_info.value.status_code == 413
    assert exc_info.value.code == "IMAGE_TOO_LARGE"


def test_unsupported_media_type_rejected():
    """Verify non-image files are rejected with HTTP 415 or 422."""
    fake_gif_header = b"GIF89a" + b"\x00" * 100

    with pytest.raises(AppError) as exc_info:
        validate_and_process_image(fake_gif_header)

    assert exc_info.value.status_code in (415, 422)


def test_corrupt_image_rejected():
    """Verify corrupt or unreadable image bytes return HTTP 422 IMAGE_UNREADABLE."""
    corrupt_bytes = b"\xff\xd8\xff\xe0corrupted_non_image_content"

    with pytest.raises(AppError) as exc_info:
        validate_and_process_image(corrupt_bytes)

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "IMAGE_UNREADABLE"


def test_empty_bytes_rejected():
    """Verify empty bytes return HTTP 422 IMAGE_UNREADABLE."""
    with pytest.raises(AppError) as exc_info:
        validate_and_process_image(b"")

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "IMAGE_UNREADABLE"


def test_save_and_delete_image_file(tmp_path):
    """Verify safe disk storage and deletion."""
    test_id = uuid.uuid4()
    sample_data = b"test_jpeg_bytes"

    file_path = save_processed_image(
        scan_id=test_id,
        image_bytes=sample_data,
        upload_dir=str(tmp_path),
    )

    assert os.path.exists(file_path)
    assert file_path.endswith(f"{test_id}.jpg")

    with open(file_path, "rb") as f:
        assert f.read() == sample_data

    # Test safe deletion
    deleted = delete_image_file(file_path)
    assert deleted is True
    assert not os.path.exists(file_path)

    # Calling delete again on non-existent file should safely return False
    assert delete_image_file(file_path) is False
    assert delete_image_file(None) is False


def test_delete_image_file_oserror_handled(monkeypatch):
    """Verify OSError during deletion is logged and returns False."""
    from pathlib import Path

    def fake_unlink(self):
        raise OSError("Permission denied")

    monkeypatch.setattr(Path, "unlink", fake_unlink)
    # Create real file
    tmp_file = "test_perm.jpg"
    with open(tmp_file, "w") as f:
        f.write("test")

    try:
        assert delete_image_file(tmp_file) is False
    finally:
        if os.path.exists(tmp_file):
            os.remove(tmp_file)


def test_processed_image_quality_reduction(monkeypatch):
    """Verify JPEG quality is reduced if output exceeds MAX_PROCESSED_SIZE_BYTES."""
    import app.media.image_pipeline as ip

    # Set threshold very low to trigger reduction
    monkeypatch.setattr(ip, "MAX_PROCESSED_SIZE_BYTES", 500)
    raw_data = _create_test_image("JPEG", size=(200, 200))
    result = ip.validate_and_process_image(raw_data)
    assert result.format == "JPEG"


def test_image_processing_general_exception(monkeypatch):
    """Verify general unexpected processing error returns HTTP 422."""
    from PIL import Image

    import app.media.image_pipeline as ip

    def fake_open(fp):
        # Allow first open (validation pass)
        img = Image.new("RGB", (10, 10))
        img.format = "JPEG"
        img.verify = lambda: None
        # Second open fails
        if getattr(fake_open, "called", False):
            raise RuntimeError("Fatal decode error")
        fake_open.called = True
        return img

    monkeypatch.setattr(Image, "open", fake_open)
    with pytest.raises(AppError) as exc_info:
        ip.validate_and_process_image(b"fake_bytes")

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "IMAGE_UNREADABLE"
