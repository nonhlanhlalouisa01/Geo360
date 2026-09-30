import { useCallback, useEffect, useRef, useState } from 'react'

export type CameraStatus = 'idle' | 'starting' | 'active' | 'error'

export interface UseCamera {
  status: CameraStatus
  error: string | null
  videoRef: React.RefObject<HTMLVideoElement | null>
  start: () => Promise<void>
  stop: () => void
  capture: () => Promise<Blob>
}

function describeCameraError(error: unknown): string {
  const name = error instanceof DOMException ? error.name : ''
  switch (name) {
    case 'NotAllowedError':
    case 'SecurityError':
      return 'Camera permission denied — allow access or upload a photo.'
    case 'NotFoundError':
    case 'OverconstrainedError':
      return 'No camera found — upload a photo instead.'
    case 'NotReadableError':
      return 'Camera is in use by another app — close it and retry.'
    default:
      return 'Camera could not start — upload a photo instead.'
  }
}

/**
 * Manages the camera stream and guarantees that every media track is stopped
 * on `stop()` and on unmount, so the device indicator never stays on.
 */
export function useCamera(): UseCamera {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [status, setStatus] = useState<CameraStatus>('idle')
  const [error, setError] = useState<string | null>(null)

  const releaseStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
  }, [])

  const stop = useCallback(() => {
    releaseStream()
    setStatus('idle')
    setError(null)
  }, [releaseStream])

  const start = useCallback(async () => {
    if (typeof window !== 'undefined' && window.isSecureContext === false) {
      setStatus('error')
      setError('Camera needs HTTPS or localhost — upload a photo instead.')
      return
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus('error')
      setError('Camera not supported in this browser — upload a photo instead.')
      return
    }

    setStatus('starting')
    setError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: 'environment' } },
        audio: false,
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play?.().catch(() => undefined)
      }
      setStatus('active')
    } catch (cameraError) {
      releaseStream()
      setStatus('error')
      setError(describeCameraError(cameraError))
    }
  }, [releaseStream])

  const capture = useCallback(async () => {
    const video = videoRef.current
    if (!video || !streamRef.current) throw new Error('Camera is not running.')

    const width = video.videoWidth || 1280
    const height = video.videoHeight || 720
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const context = canvas.getContext('2d')
    if (!context) throw new Error('Cannot capture from this browser — upload a photo instead.')
    context.drawImage(video, 0, 0, width, height)

    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob(resolve, 'image/jpeg', 0.92)
    })
    if (!blob) throw new Error('Capture failed — try again.')
    return blob
  }, [])

  useEffect(() => releaseStream, [releaseStream])

  return { status, error, videoRef, start, stop, capture }
}
