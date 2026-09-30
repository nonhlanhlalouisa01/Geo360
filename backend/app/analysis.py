"""Deterministic OpenCV image-quality screening.

Scope and honesty
-----------------
This module measures **photographic quality only**: size, exposure, clipping
and focus. Those measurements say nothing about mineralogy, grade, hardness,
moisture, particle size, recovery or plant suitability, and a sharp, well-lit
photograph is not evidence that the photographed object is ore.

Processing readiness is therefore reported separately and always fails closed
(:func:`assess_readiness`) until a site-validated ore classifier and a
calibrated plant policy are supplied.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import cv2
import numpy as np

from .config import Settings
from .imaging import ImageHeader

METHOD = "opencv-image-quality-screening"
METHOD_VERSION = "0.1.0"

#: Grayscale level at or below which a pixel counts as "near black".
DARK_LEVEL = 25
#: Grayscale level at or above which a pixel counts as "blown out".
CLIPPED_LEVEL = 250

LIMITATIONS: tuple[str, ...] = (
    "Measures photo quality only: exposure, clipping, focus and size.",
    "Does not identify ore, mineralogy, grade, hardness, moisture or particle size.",
    "Thresholds are illustrative defaults, not calibrated to any site or camera.",
    "Processing readiness always requires plant validation and lab assays.",
)


@dataclass(frozen=True)
class QualityMetrics:
    """Measured, reproducible values taken directly from the decoded image."""

    width: int
    height: int
    mean_brightness: float
    dark_fraction: float
    clipped_fraction: float
    sharpness: float

    def as_dict(self) -> dict[str, float | int]:
        return asdict(self)


@dataclass(frozen=True)
class Verdict:
    """Outcome of one check: a status plus a short, actionable reason."""

    status: str
    reason: str


def measure(image: np.ndarray) -> QualityMetrics:
    """Compute deterministic quality metrics for a decoded BGR image."""

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape[:2]
    pixels = float(gray.size)

    return QualityMetrics(
        width=int(width),
        height=int(height),
        mean_brightness=round(float(gray.mean()), 2),
        dark_fraction=round(float(np.count_nonzero(gray <= DARK_LEVEL) / pixels), 4),
        clipped_fraction=round(
            float(np.count_nonzero(gray >= CLIPPED_LEVEL) / pixels), 4
        ),
        sharpness=round(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 2),
    )


def assess_quality(metrics: QualityMetrics, settings: Settings) -> Verdict:
    """Apply the configured thresholds to the measured metrics.

    The first failing check wins, so the user is given one clear action.
    """

    if metrics.mean_brightness < settings.min_mean_brightness:
        return Verdict("fail", "Image too dark — improve lighting.")
    if metrics.mean_brightness > settings.max_mean_brightness:
        return Verdict("fail", "Image too bright — reduce glare or exposure.")
    if metrics.dark_fraction > settings.max_dark_fraction:
        return Verdict("fail", "Too much of the frame is in shadow — light the sample evenly.")
    if metrics.clipped_fraction > settings.max_clipped_fraction:
        return Verdict("fail", "Highlights are blown out — move the light source or reduce flash.")
    if metrics.sharpness < settings.min_sharpness:
        return Verdict("fail", "Image is blurred — hold steady and refocus.")
    return Verdict("pass", "Visual check passed — image quality is usable.")


def assess_readiness(quality: Verdict, settings: Settings) -> Verdict:
    """Report processing readiness. Fails closed by design.

    A validated ore classifier and a plant-specific readiness policy would be
    plugged in here. Until ``readiness_policy_validated`` is switched on by an
    operator who has supplied and verified those components, the answer is
    always "unverified" — including when the image quality check passes.
    """

    if not settings.readiness_policy_validated:
        return Verdict("unverified", "Readiness unverified — plant validation required.")

    # Seam for a future validated policy. Even then, a failed image check can
    # never produce an approval, because the input evidence is unusable.
    if quality.status != "pass":
        return Verdict("unverified", "Readiness unverified — retake a usable image first.")
    raise NotImplementedError(
        "No validated ore classifier or plant readiness policy is installed."
    )


@dataclass(frozen=True)
class AnalysisResult:
    """Everything the API returns about one image."""

    visual_status: str
    visual_reason: str
    readiness_status: str
    readiness_reason: str
    metrics: QualityMetrics
    thresholds: dict[str, float]
    limitations: tuple[str, ...]
    image_format: str
    method: str
    method_version: str


def analyse(image: np.ndarray, header: ImageHeader, settings: Settings) -> AnalysisResult:
    """Run the full deterministic screening pipeline on a decoded image."""

    metrics = measure(image)
    quality = assess_quality(metrics, settings)
    readiness = assess_readiness(quality, settings)

    return AnalysisResult(
        visual_status=quality.status,
        visual_reason=quality.reason,
        readiness_status=readiness.status,
        readiness_reason=readiness.reason,
        metrics=metrics,
        thresholds={
            "min_mean_brightness": settings.min_mean_brightness,
            "max_mean_brightness": settings.max_mean_brightness,
            "max_dark_fraction": settings.max_dark_fraction,
            "max_clipped_fraction": settings.max_clipped_fraction,
            "min_sharpness": settings.min_sharpness,
        },
        limitations=LIMITATIONS,
        image_format=header.image_format,
        method=METHOD,
        method_version=METHOD_VERSION,
    )
