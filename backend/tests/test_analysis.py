"""Deterministic image-quality and readiness tests."""

from __future__ import annotations

import pytest

from app.analysis import analyse, assess_quality, assess_readiness, measure
from app.config import Settings
from app.imaging import ImageHeader

from .conftest import blurred_image, bright_image, dark_image, sharp_image

HEADER = ImageHeader("png", 320, 320)


def test_metrics_are_deterministic(settings: Settings) -> None:
    image = sharp_image()
    assert measure(image) == measure(image)


def test_sharp_well_lit_image_passes_quality(settings: Settings) -> None:
    metrics = measure(sharp_image())
    verdict = assess_quality(metrics, settings)
    assert verdict.status == "pass"
    assert verdict.reason == "Visual check passed — image quality is usable."
    assert metrics.width == 320 and metrics.height == 320


def test_dark_image_fails_with_lighting_reason(settings: Settings) -> None:
    verdict = assess_quality(measure(dark_image()), settings)
    assert verdict.status == "fail"
    assert verdict.reason == "Image too dark — improve lighting."


def test_bright_image_fails_with_exposure_reason(settings: Settings) -> None:
    verdict = assess_quality(measure(bright_image()), settings)
    assert verdict.status == "fail"
    assert "bright" in verdict.reason.lower()


def test_blurred_image_fails_with_focus_reason(settings: Settings) -> None:
    metrics = measure(blurred_image())
    verdict = assess_quality(metrics, settings)
    assert verdict.status == "fail"
    assert "blurred" in verdict.reason.lower()
    assert metrics.sharpness < settings.min_sharpness


def test_shadowed_image_fails_on_dark_fraction(settings: Settings) -> None:
    image = sharp_image()
    image[:, :260] = 0  # most of the frame in deep shadow
    tolerant = settings.model_copy(update={"min_mean_brightness": 0.0})
    verdict = assess_quality(measure(image), tolerant)
    assert verdict.status == "fail"
    assert "shadow" in verdict.reason.lower()


def test_clipped_highlights_fail(settings: Settings) -> None:
    image = sharp_image()
    image[:, :150] = 255
    tolerant = settings.model_copy(update={"max_mean_brightness": 255.0})
    verdict = assess_quality(measure(image), tolerant)
    assert verdict.status == "fail"
    assert "blown out" in verdict.reason.lower()


@pytest.mark.parametrize("factory", [sharp_image, dark_image, blurred_image, bright_image])
def test_readiness_always_fails_closed(factory, settings: Settings) -> None:
    result = analyse(factory(), HEADER, settings)
    assert result.readiness_status == "unverified"
    assert result.readiness_reason == "Readiness unverified — plant validation required."


def test_passing_quality_never_claims_processing_approval(settings: Settings) -> None:
    result = analyse(sharp_image(), HEADER, settings)
    assert result.visual_status == "pass"
    text = f"{result.visual_reason} {result.readiness_reason}".lower()
    assert "ready for processing" not in text
    assert result.readiness_status != "ready"
    assert result.limitations


def test_readiness_seam_rejects_failed_quality_even_if_policy_enabled(settings: Settings) -> None:
    enabled = settings.model_copy(update={"readiness_policy_validated": True})
    verdict = assess_readiness(assess_quality(measure(dark_image()), enabled), enabled)
    assert verdict.status == "unverified"


def test_readiness_seam_is_not_implemented_for_passing_quality(settings: Settings) -> None:
    enabled = settings.model_copy(update={"readiness_policy_validated": True})
    quality = assess_quality(measure(sharp_image()), enabled)
    with pytest.raises(NotImplementedError):
        assess_readiness(quality, enabled)


def test_analysis_reports_method_and_thresholds(settings: Settings) -> None:
    result = analyse(sharp_image(), HEADER, settings)
    assert result.method_version
    assert result.thresholds["min_sharpness"] == settings.min_sharpness
