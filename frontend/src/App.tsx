import { useCallback, useEffect, useRef, useState } from 'react'
import './App.css'
import { ApiError, UPLOAD_LIMITS, analyseImage, type AnalysisResponse } from './api'
import { useCamera } from './useCamera'
import { Verdict } from './Verdict'

const ACCEPT = UPLOAD_LIMITS.acceptedTypes.join(',')

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

export default function App() {
  const {
    status: cameraStatus,
    error: cameraError,
    videoRef,
    start: startCamera,
    stop: stopCamera,
    capture: captureFrame,
  } = useCamera()
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [result, setResult] = useState<AnalysisResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isAnalysing, setIsAnalysing] = useState(false)

  const previewUrlRef = useRef<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const setPreview = useCallback((blob: Blob | null) => {
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current)
    const url = blob ? URL.createObjectURL(blob) : null
    previewUrlRef.current = url
    setPreviewUrl(url)
  }, [])

  useEffect(
    () => () => {
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current)
      abortRef.current?.abort()
    },
    [],
  )

  const submit = useCallback(
    async (blob: Blob, filename: string) => {
      if (abortRef.current) return // one analysis at a time
      const controller = new AbortController()
      abortRef.current = controller

      // Drop any previous verdict immediately so a stale result is never shown
      // beside a new image.
      setResult(null)
      setError(null)
      setPreview(blob)
      setIsAnalysing(true)
      try {
        const response = await analyseImage(blob, filename, controller.signal)
        if (!controller.signal.aborted) setResult(response)
      } catch (submitError) {
        if (!controller.signal.aborted) {
          setError(
            submitError instanceof ApiError ? submitError.message : 'Analysis failed — try again.',
          )
        }
      } finally {
        if (abortRef.current === controller) abortRef.current = null
        setIsAnalysing(false)
      }
    },
    [setPreview],
  )

  const handleCapture = useCallback(async () => {
    try {
      const blob = await captureFrame()
      await submit(blob, 'capture.jpg')
    } catch (captureError) {
      setError(captureError instanceof Error ? captureError.message : 'Capture failed — try again.')
    }
  }, [captureFrame, submit])

  const handleFile = useCallback(
    async (file: File | undefined) => {
      if (!file) return
      if (!(UPLOAD_LIMITS.acceptedTypes as readonly string[]).includes(file.type)) {
        setResult(null)
        setPreview(null)
        setError('Unsupported file type — use JPEG, PNG, WebP or BMP.')
        return
      }
      if (file.size > UPLOAD_LIMITS.maxBytes) {
        setResult(null)
        setPreview(null)
        setError(`File too large — keep it under ${UPLOAD_LIMITS.maxBytes / 1_000_000} MB.`)
        return
      }
      await submit(file, file.name)
    },
    [setPreview, submit],
  )

  const reset = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setIsAnalysing(false)
    setResult(null)
    setError(null)
    setPreview(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }, [setPreview])

  return (
    <div className="page">
      <header className="page__header">
        <h1>GeoMet360 — ore visual screening</h1>
        <p className="page__subtitle">
          Photograph a sample to check whether the image is good enough for review. This is an
          image-quality check only: it does not identify ore and never approves processing.
        </p>
      </header>

      <main className="layout">
        <section className="panel" aria-labelledby="capture-heading">
          <h2 id="capture-heading">1. Capture a sample</h2>

          <div className="stage">
            <video
              ref={videoRef}
              className="stage__media"
              hidden={cameraStatus !== 'active'}
              playsInline
              muted
              autoPlay
              aria-label="Live camera preview"
            />
            {cameraStatus !== 'active' && previewUrl && (
              <img className="stage__media" src={previewUrl} alt="Captured sample" />
            )}
            {cameraStatus !== 'active' && !previewUrl && (
              <p className="stage__empty">Start the camera or upload a photo to begin.</p>
            )}
          </div>

          <div className="controls">
            {cameraStatus !== 'active' ? (
              <button
                type="button"
                className="button button--primary"
                onClick={() => void startCamera()}
                disabled={cameraStatus === 'starting'}
              >
                {cameraStatus === 'starting' ? 'Starting camera…' : 'Start camera'}
              </button>
            ) : (
              <>
                <button
                  type="button"
                  className="button button--primary"
                  onClick={() => void handleCapture()}
                  disabled={isAnalysing}
                >
                  {isAnalysing ? 'Analysing…' : 'Capture and analyse'}
                </button>
                <button type="button" className="button" onClick={stopCamera}>
                  Stop camera
                </button>
              </>
            )}

            <label className="button button--ghost">
              Upload a photo
              <input
                ref={fileInputRef}
                type="file"
                accept={ACCEPT}
                className="visually-hidden"
                disabled={isAnalysing}
                onChange={(event) => void handleFile(event.target.files?.[0])}
              />
            </label>

            <button
              type="button"
              className="button button--ghost"
              onClick={reset}
              disabled={isAnalysing || (!previewUrl && !result && !error)}
            >
              Reset
            </button>
          </div>

          <p className="hint">
            The browser asks for camera permission the first time. Camera access needs HTTPS (or
            localhost). Images are analysed in memory and are never stored.
          </p>
        </section>

        <section className="panel" aria-labelledby="result-heading" aria-busy={isAnalysing}>
          <h2 id="result-heading">2. Result</h2>

          {cameraError && <p className="alert alert--warning">{cameraError}</p>}
          {error && <p className="alert alert--error">{error}</p>}
          {isAnalysing && <p className="alert">Analysing image…</p>}
          {!result && !isAnalysing && !error && <p className="hint">No image analysed yet.</p>}

          {result && !isAnalysing && (
            <div className="results">
              <Verdict
                tone={result.visual_status === 'pass' ? 'pass' : 'fail'}
                label={result.visual_status === 'pass' ? 'Pass' : 'Fail'}
                title="Image quality check"
                reason={result.visual_reason}
              />
              <Verdict
                tone="fail"
                label="Unverified"
                title="Processing readiness"
                reason={result.readiness_reason}
              />

              <details className="details">
                <summary>Measured metrics</summary>
                <dl className="metrics">
                  <div>
                    <dt>Resolution</dt>
                    <dd>
                      {result.metrics.width} × {result.metrics.height} px
                    </dd>
                  </div>
                  <div>
                    <dt>Mean brightness (0–255)</dt>
                    <dd>{result.metrics.mean_brightness}</dd>
                  </div>
                  <div>
                    <dt>Dark pixels</dt>
                    <dd>{formatPercent(result.metrics.dark_fraction)}</dd>
                  </div>
                  <div>
                    <dt>Clipped pixels</dt>
                    <dd>{formatPercent(result.metrics.clipped_fraction)}</dd>
                  </div>
                  <div>
                    <dt>Sharpness (Laplacian variance)</dt>
                    <dd>{result.metrics.sharpness}</dd>
                  </div>
                  <div>
                    <dt>Method</dt>
                    <dd>
                      {result.method} v{result.method_version}
                    </dd>
                  </div>
                </dl>
              </details>

              <div className="limitations">
                <h3>Limitations</h3>
                <ul>
                  {result.limitations.map((limitation) => (
                    <li key={limitation}>{limitation}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </section>
      </main>

      <footer className="page__footer">
        <p>
          GeoMet360 screening prototype. The recovery, throughput, energy and water predictions
          described in the project vision are <strong>not</strong> implemented here.
        </p>
      </footer>
    </div>
  )
}
