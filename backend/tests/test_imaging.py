"""Validation tests for untrusted image bytes."""

from __future__ import annotations

import struct

import numpy as np
import pytest

from app.config import Settings
from app.imaging import ImageValidationError, decode_image, read_header

from .conftest import encode, sharp_image


def test_decodes_supported_formats(settings: Settings) -> None:
    for ext, expected in ((".png", "png"), (".jpg", "jpeg"), (".bmp", "bmp"), (".webp", "webp")):
        image, header = decode_image(encode(sharp_image(), ext), settings)
        assert header.image_format == expected
        assert image.shape[:2] == (320, 320)


def test_empty_bytes_rejected(settings: Settings) -> None:
    with pytest.raises(ImageValidationError) as excinfo:
        decode_image(b"", settings)
    assert excinfo.value.code == "empty_file"


def test_non_image_bytes_rejected(settings: Settings) -> None:
    with pytest.raises(ImageValidationError) as excinfo:
        decode_image(b"this is definitely not an image", settings)
    assert excinfo.value.code == "unsupported_format"


def test_truncated_png_rejected(settings: Settings) -> None:
    data = encode(sharp_image())
    with pytest.raises(ImageValidationError) as excinfo:
        decode_image(data[:60], settings)
    assert excinfo.value.code == "corrupt_image"


def test_oversized_byte_payload_rejected(settings: Settings) -> None:
    tiny = settings.model_copy(update={"max_upload_bytes": 100})
    with pytest.raises(ImageValidationError) as excinfo:
        decode_image(encode(sharp_image()), tiny)
    assert excinfo.value.code == "file_too_large"


def test_image_below_minimum_dimension_rejected(settings: Settings) -> None:
    small = np.full((32, 32, 3), 128, dtype=np.uint8)
    with pytest.raises(ImageValidationError) as excinfo:
        decode_image(encode(small), settings)
    assert excinfo.value.code == "image_too_small"


def test_oversized_dimensions_rejected_from_header(settings: Settings) -> None:
    strict = settings.model_copy(update={"max_image_dimension": 128})
    with pytest.raises(ImageValidationError) as excinfo:
        decode_image(encode(sharp_image()), strict)
    assert excinfo.value.code == "image_too_large"


def test_pixel_count_limit_rejected_before_decode(settings: Settings) -> None:
    """A forged PNG header is refused without ever allocating the pixel buffer."""

    data = bytearray(encode(sharp_image()))
    data[16:24] = struct.pack(">II", 30_000, 30_000)
    header = read_header(bytes(data))
    assert header.width * header.height > settings.max_image_pixels
    with pytest.raises(ImageValidationError) as excinfo:
        decode_image(bytes(data), settings)
    assert excinfo.value.code == "image_too_large"


def test_error_messages_are_short_and_actionable(settings: Settings) -> None:
    with pytest.raises(ImageValidationError) as excinfo:
        decode_image(b"nope", settings)
    message = excinfo.value.message
    assert len(message) < 120
    assert "Traceback" not in message
