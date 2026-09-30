"""FastAPI application exposing the GeoMet360 visual screening endpoints.

Privacy: uploaded images are held in memory for the duration of the request
only. Nothing is persisted, no raw image bytes are logged, and no third-party
service is contacted.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__
from .analysis import METHOD, METHOD_VERSION, analyse
from .config import Settings, get_settings
from .imaging import SUPPORTED_FORMATS, ImageValidationError, decode_image
from .schemas import AnalysisResponse, ErrorResponse, HealthResponse, LimitsModel

logger = logging.getLogger("geomet360")

_TOO_LARGE_CODES = {"file_too_large", "image_too_large"}


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(code=code, message=message).model_dump(),
    )


async def _read_bounded(upload: UploadFile, limit: int) -> bytes:
    """Read an upload, stopping as soon as the byte budget is exceeded."""

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise ImageValidationError(
                "file_too_large",
                f"File too large. Keep the image under {limit / 1_000_000:.1f} MB.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application. Tests can inject custom settings."""

    settings = settings or get_settings()

    app = FastAPI(
        title="GeoMet360 ore visual screening API",
        version=__version__,
        description=(
            "Deterministic OpenCV image-quality screening. It does not identify "
            "ore and never approves processing readiness."
        ),
    )
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def limit_body_size(request: Request, call_next):
        declared = request.headers.get("content-length")
        if declared is not None:
            try:
                length = int(declared)
            except ValueError:
                return _error(400, "invalid_request", "Malformed request. Try again.")
            # Allow headroom for multipart boundaries around the file itself.
            if length > settings.max_upload_bytes + 64 * 1024:
                return _error(
                    413,
                    "file_too_large",
                    "File too large. Keep the image under "
                    f"{settings.max_upload_bytes / 1_000_000:.1f} MB.",
                )
        return await call_next(request)

    @app.exception_handler(ImageValidationError)
    async def handle_validation_error(_: Request, exc: ImageValidationError) -> JSONResponse:
        status_code = 413 if exc.code in _TOO_LARGE_CODES else 400
        return _error(status_code, exc.code, exc.message)

    @app.get("/api/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            version=__version__,
            method=METHOD,
            method_version=METHOD_VERSION,
            readiness_policy_validated=settings.readiness_policy_validated,
            limits=LimitsModel(
                max_upload_bytes=settings.max_upload_bytes,
                max_image_pixels=settings.max_image_pixels,
                max_image_dimension=settings.max_image_dimension,
                min_image_dimension=settings.min_image_dimension,
                supported_formats=sorted(SUPPORTED_FORMATS.values()),
            ),
        )

    @app.post(
        "/api/analyze",
        response_model=AnalysisResponse,
        responses={400: {"model": ErrorResponse}, 413: {"model": ErrorResponse}},
    )
    async def analyze(image: UploadFile = File(...)) -> AnalysisResponse:
        data = await _read_bounded(image, settings.max_upload_bytes)
        decoded, header = decode_image(data, settings)
        try:
            result = analyse(decoded, header, settings)
        except ImageValidationError:
            raise
        except Exception:  # pragma: no cover - defensive, never leaks internals
            logger.exception("Image analysis failed")
            return JSONResponse(  # type: ignore[return-value]
                status_code=500,
                content=ErrorResponse(
                    code="analysis_failed",
                    message="Analysis failed. Try again with another image.",
                ).model_dump(),
            )

        return AnalysisResponse(
            visual_status=result.visual_status,
            visual_reason=result.visual_reason,
            readiness_status=result.readiness_status,
            readiness_reason=result.readiness_reason,
            metrics=result.metrics.as_dict(),  # type: ignore[arg-type]
            thresholds=result.thresholds,
            limitations=list(result.limitations),
            image_format=result.image_format,
            method=result.method,
            method_version=result.method_version,
        )

    return app


app = create_app()
