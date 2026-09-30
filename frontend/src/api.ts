/**
 * Client for the GeoMet360 screening API.
 *
 * The base URL comes from `VITE_API_BASE_URL`. When it is empty the requests
 * go to a relative `/api/...` path, which the Vite dev server proxies to the
 * backend (see `vite.config.ts`).
 */

export interface Metrics {
  width: number
  height: number
  mean_brightness: number
  dark_fraction: number
  clipped_fraction: number
  sharpness: number
}

export type VisualStatus = 'pass' | 'fail'
export type ReadinessStatus = 'unverified' | 'ready' | 'not_ready'

export interface AnalysisResponse {
  visual_status: VisualStatus
  visual_reason: string
  readiness_status: ReadinessStatus
  readiness_reason: string
  metrics: Metrics
  thresholds: Record<string, number>
  limitations: string[]
  image_format: string
  method: string
  method_version: string
}

export class ApiError extends Error {
  readonly code: string

  constructor(code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.code = code
  }
}

const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

/** Upload settings kept deliberately aligned with the backend defaults. */
export const UPLOAD_LIMITS = {
  maxBytes: 8_000_000,
  acceptedTypes: ['image/jpeg', 'image/png', 'image/webp', 'image/bmp'],
} as const

export async function analyseImage(
  image: Blob,
  filename: string,
  signal?: AbortSignal,
): Promise<AnalysisResponse> {
  const body = new FormData()
  body.append('image', image, filename)

  let response: Response
  try {
    response = await fetch(`${baseUrl}/api/analyze`, { method: 'POST', body, signal })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError('network_error', 'Cannot reach the analysis service — check it is running.')
  }

  if (!response.ok) {
    let message = 'Analysis failed — try again.'
    let code = 'request_failed'
    try {
      const payload = (await response.json()) as { code?: string; message?: string }
      if (typeof payload.message === 'string' && payload.message) message = payload.message
      if (typeof payload.code === 'string' && payload.code) code = payload.code
    } catch {
      /* keep the generic message when the body is not JSON */
    }
    throw new ApiError(code, message)
  }

  return (await response.json()) as AnalysisResponse
}
