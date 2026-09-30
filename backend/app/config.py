"""Runtime configuration for the GeoMet360 screening backend.

All values are illustrative defaults and can be overridden with environment
variables prefixed with ``GEOMET360_`` (see ``backend/.env.example``).

The image-quality thresholds are **not** calibrated against any mine site,
camera or ore body. They only describe whether a photograph is usable for
human review, never whether the photographed material is ore.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven settings."""

    model_config = SettingsConfigDict(
        env_prefix="GEOMET360_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- CORS -------------------------------------------------------------
    allowed_origins: list[str] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173"],
        description="Explicit list of browser origins allowed to call the API.",
    )

    # --- Request / decode limits -----------------------------------------
    max_upload_bytes: int = Field(
        default=8_000_000,
        gt=0,
        description="Largest accepted request body for an image upload.",
    )
    max_image_pixels: int = Field(
        default=40_000_000,
        gt=0,
        description="Largest accepted decoded pixel count (decompression-bomb guard).",
    )
    max_image_dimension: int = Field(
        default=10_000,
        gt=0,
        description="Largest accepted width or height in pixels.",
    )
    min_image_dimension: int = Field(
        default=64,
        gt=0,
        description="Smallest accepted width or height in pixels.",
    )

    # --- Illustrative image-quality thresholds ---------------------------
    min_mean_brightness: float = Field(
        default=45.0, description="Minimum mean grayscale level (0-255)."
    )
    max_mean_brightness: float = Field(
        default=215.0, description="Maximum mean grayscale level (0-255)."
    )
    max_dark_fraction: float = Field(
        default=0.55, ge=0.0, le=1.0, description="Maximum fraction of near-black pixels."
    )
    max_clipped_fraction: float = Field(
        default=0.25, ge=0.0, le=1.0, description="Maximum fraction of blown-out pixels."
    )
    min_sharpness: float = Field(
        default=60.0, ge=0.0, description="Minimum variance of the Laplacian."
    )

    # --- Readiness policy -------------------------------------------------
    readiness_policy_validated: bool = Field(
        default=False,
        description=(
            "Fail-closed switch. Stays False until a site-validated ore classifier "
            "and plant-specific readiness policy are supplied and independently "
            "verified. The API never approves processing readiness while False."
        ),
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings so the app reads the environment once."""

    return Settings()
