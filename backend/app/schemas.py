"""Typed request/response models for the screening API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

VisualStatus = Literal["pass", "fail"]
ReadinessStatus = Literal["unverified", "ready", "not_ready"]


class MetricsModel(BaseModel):
    """Measured image-quality values."""

    width: int = Field(description="Decoded image width in pixels.")
    height: int = Field(description="Decoded image height in pixels.")
    mean_brightness: float = Field(description="Mean grayscale level, 0-255.")
    dark_fraction: float = Field(description="Fraction of near-black pixels.")
    clipped_fraction: float = Field(description="Fraction of blown-out pixels.")
    sharpness: float = Field(description="Variance of the Laplacian (focus proxy).")


class AnalysisResponse(BaseModel):
    """Result of one image screening request."""

    visual_status: VisualStatus
    visual_reason: str
    readiness_status: ReadinessStatus
    readiness_reason: str
    metrics: MetricsModel
    thresholds: dict[str, float]
    limitations: list[str]
    image_format: str
    method: str
    method_version: str


class LimitsModel(BaseModel):
    """Upload limits, so the frontend can reject oversized files early."""

    max_upload_bytes: int
    max_image_pixels: int
    max_image_dimension: int
    min_image_dimension: int
    supported_formats: list[str]


class HealthResponse(BaseModel):
    """Liveness and capability information."""

    status: Literal["ok"]
    version: str
    method: str
    method_version: str
    readiness_policy_validated: bool
    limits: LimitsModel


class ErrorResponse(BaseModel):
    """Short, caller-safe error payload."""

    code: str
    message: str
