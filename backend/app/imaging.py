"""Safe image decoding helpers.

Untrusted bytes are validated in stages before anything expensive happens:

1. non-empty and within the configured byte budget;
2. the container format is sniffed from magic bytes (the declared MIME type of
   an upload is never trusted);
3. the pixel dimensions are read from the container header and checked against
   the configured bounds, so a decompression bomb is rejected *before* a large
   buffer is allocated;
4. only then are the bytes handed to OpenCV for the real decode, and the
   decoded array is re-checked because a header can lie.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

import cv2
import numpy as np

from .config import Settings

#: Container formats the API accepts. Keep in sync with the frontend accept list.
SUPPORTED_FORMATS: dict[str, str] = {
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "bmp": "image/bmp",
}


class ImageValidationError(ValueError):
    """Raised when untrusted bytes cannot be accepted as an image.

    The message is safe to return to the caller: it never contains library
    internals, file paths or raw image data.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ImageHeader:
    """Container format and declared pixel dimensions."""

    image_format: str
    width: int
    height: int


def _sniff_format(data: bytes) -> str:
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:2] == b"BM":
        return "bmp"
    raise ImageValidationError(
        "unsupported_format",
        "Unsupported file type. Use a JPEG, PNG, WebP or BMP image.",
    )


def _corrupt(detail: str = "") -> ImageValidationError:
    message = "Image file is corrupt or incomplete."
    if detail:
        message = f"{message} {detail}"
    return ImageValidationError("corrupt_image", message)


def _png_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or data[12:16] != b"IHDR":
        raise _corrupt()
    width, height = struct.unpack(">II", data[16:24])
    return int(width), int(height)


def _bmp_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 26:
        raise _corrupt()
    width, height = struct.unpack("<ii", data[18:26])
    return abs(int(width)), abs(int(height))


def _webp_dimensions(data: bytes) -> tuple[int, int]:
    chunk = data[12:16]
    if chunk == b"VP8X" and len(data) >= 30:
        width = int.from_bytes(data[24:27], "little") + 1
        height = int.from_bytes(data[27:30], "little") + 1
        return width, height
    if chunk == b"VP8L" and len(data) >= 25:
        bits = int.from_bytes(data[21:25], "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return width, height
    if chunk == b"VP8 " and len(data) >= 30:
        width = int.from_bytes(data[26:28], "little") & 0x3FFF
        height = int.from_bytes(data[28:30], "little") & 0x3FFF
        return width, height
    raise _corrupt()


_JPEG_SOF_MARKERS = {
    0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
    0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
}


def _jpeg_dimensions(data: bytes) -> tuple[int, int]:
    index = 2
    total = len(data)
    while index + 3 < total:
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        index += 2
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            continue
        if index + 1 >= total:
            break
        segment_length = struct.unpack(">H", data[index : index + 2])[0]
        if segment_length < 2:
            raise _corrupt()
        if marker in _JPEG_SOF_MARKERS:
            if index + 7 > total:
                raise _corrupt()
            height, width = struct.unpack(">HH", data[index + 3 : index + 7])
            return int(width), int(height)
        index += segment_length
    raise _corrupt()


_DIMENSION_READERS = {
    "jpeg": _jpeg_dimensions,
    "png": _png_dimensions,
    "webp": _webp_dimensions,
    "bmp": _bmp_dimensions,
}


def read_header(data: bytes) -> ImageHeader:
    """Sniff the container format and read its declared dimensions."""

    image_format = _sniff_format(data)
    width, height = _DIMENSION_READERS[image_format](data)
    return ImageHeader(image_format=image_format, width=width, height=height)


def _check_dimensions(width: int, height: int, settings: Settings) -> None:
    if width <= 0 or height <= 0:
        raise _corrupt()
    if width < settings.min_image_dimension or height < settings.min_image_dimension:
        raise ImageValidationError(
            "image_too_small",
            f"Image too small. Use at least {settings.min_image_dimension}px on each side.",
        )
    if width > settings.max_image_dimension or height > settings.max_image_dimension:
        raise ImageValidationError(
            "image_too_large",
            f"Image too large. Keep width and height under {settings.max_image_dimension}px.",
        )
    if width * height > settings.max_image_pixels:
        raise ImageValidationError(
            "image_too_large",
            f"Image has too many pixels. Limit is {settings.max_image_pixels} pixels.",
        )


def decode_image(data: bytes, settings: Settings) -> tuple[np.ndarray, ImageHeader]:
    """Validate untrusted bytes and decode them into a BGR array.

    Raises:
        ImageValidationError: with a short, caller-safe message.
    """

    if not data:
        raise ImageValidationError("empty_file", "No image data received. Try again.")
    if len(data) > settings.max_upload_bytes:
        limit_mb = settings.max_upload_bytes / 1_000_000
        raise ImageValidationError(
            "file_too_large",
            f"File too large. Keep the image under {limit_mb:.1f} MB.",
        )

    header = read_header(data)
    _check_dimensions(header.width, header.height, settings)

    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        raise _corrupt()

    height, width = image.shape[:2]
    _check_dimensions(width, height, settings)
    return image, ImageHeader(header.image_format, width, height)
