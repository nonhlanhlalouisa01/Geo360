"""Shared synthetic image fixtures.

Every image here is generated deterministically with NumPy/OpenCV. They are
clearly synthetic test material and are never presented as real ore samples.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.config import Settings


def encode(image: np.ndarray, ext: str = ".png") -> bytes:
    ok, buffer = cv2.imencode(ext, image)
    assert ok, "failed to encode synthetic test image"
    return buffer.tobytes()


def sharp_image(size: int = 320, level: int = 130) -> np.ndarray:
    """A mid-grey frame with a high-contrast checkerboard (high Laplacian variance)."""

    image = np.full((size, size, 3), level, dtype=np.uint8)
    block = 16
    for row in range(0, size, block):
        for col in range(0, size, block):
            if ((row // block) + (col // block)) % 2 == 0:
                image[row : row + block, col : col + block] = max(level - 70, 0)
    return image


def blurred_image(size: int = 320) -> np.ndarray:
    return cv2.GaussianBlur(sharp_image(size), (61, 61), 0)


def dark_image(size: int = 320) -> np.ndarray:
    return np.full((size, size, 3), 5, dtype=np.uint8)


def bright_image(size: int = 320) -> np.ndarray:
    return np.full((size, size, 3), 253, dtype=np.uint8)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        allowed_origins=["http://localhost:5173"],
        max_upload_bytes=2_000_000,
        max_image_pixels=1_000_000,
        max_image_dimension=1_000,
        min_image_dimension=64,
    )
