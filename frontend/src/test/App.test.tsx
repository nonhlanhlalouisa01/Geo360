import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import type { AnalysisResponse } from '../api'

function buildResponse(overrides: Partial<AnalysisResponse> = {}): AnalysisResponse {
  return {
    visual_status: 'pass',
    visual_reason: 'Visual check passed — image quality is usable.',
    readiness_status: 'unverified',
    readiness_reason: 'Readiness unverified — plant validation required.',
    metrics: {
      width: 640,
      height: 480,
      mean_brightness: 128.5,
      dark_fraction: 0.02,
      clipped_fraction: 0.01,
      sharpness: 412.3,
    },
    thresholds: { min_sharpness: 60 },
    limitations: ['Measures photo quality only: exposure, clipping, focus and size.'],
    image_format: 'jpeg',
    method: 'opencv-image-quality-screening',
    method_version: '0.1.0',
    ...overrides,
  }
}

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response
}

function uploadFile(file: File) {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement
  fireEvent.change(input, { target: { files: [file] } })
}

function pngFile(name = 'sample.png', size = 1024): File {
  const file = new File([new Uint8Array(size)], name, { type: 'image/png' })
  Object.defineProperty(file, 'size', { value: size })
  return file
}

const createObjectURL = vi.fn(() => 'blob:preview')
const revokeObjectURL = vi.fn()

beforeEach(() => {
  createObjectURL.mockClear()
  revokeObjectURL.mockClear()
  Object.assign(URL, { createObjectURL, revokeObjectURL })
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('GeoMet360 screening app', () => {
  it('shows the camera start control and a scope disclaimer', () => {
    render(<App />)
    expect(screen.getByRole('button', { name: 'Start camera' })).toBeInTheDocument()
    expect(screen.getByText(/does not identify ore/i)).toBeInTheDocument()
  })

  it('renders a pass verdict with a short reason and a fail-closed readiness verdict', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(buildResponse())))
    render(<App />)
    uploadFile(pngFile())

    await waitFor(() => expect(screen.getByText(/Image quality check/)).toBeInTheDocument())
    expect(screen.getByText('Pass')).toBeInTheDocument()
    expect(screen.getByText('Visual check passed — image quality is usable.')).toBeInTheDocument()

    // Readiness must never be approved by the visual check alone.
    expect(screen.getByText('Unverified')).toBeInTheDocument()
    expect(
      screen.getByText('Readiness unverified — plant validation required.'),
    ).toBeInTheDocument()
    expect(screen.queryByText(/ready for processing/i)).not.toBeInTheDocument()
  })

  it('renders a fail verdict with the backend reason', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse(
          buildResponse({
            visual_status: 'fail',
            visual_reason: 'Image too dark — improve lighting.',
          }),
        ),
      ),
    )
    render(<App />)
    uploadFile(pngFile())

    await waitFor(() =>
      expect(screen.getByText('Image too dark — improve lighting.')).toBeInTheDocument(),
    )
    expect(screen.getByText('Fail')).toBeInTheDocument()
  })

  it('shows measured metrics and limitations', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(buildResponse())))
    render(<App />)
    uploadFile(pngFile())

    await waitFor(() => expect(screen.getByText('Measured metrics')).toBeInTheDocument())
    expect(screen.getByText('640 × 480 px')).toBeInTheDocument()
    expect(screen.getByText('412.3')).toBeInTheDocument()
    expect(screen.getByText(/Measures photo quality only/)).toBeInTheDocument()
  })

  it('rejects unsupported file types without calling the API', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    uploadFile(new File(['text'], 'notes.txt', { type: 'text/plain' }))

    await waitFor(() =>
      expect(
        screen.getByText('Unsupported file type — use JPEG, PNG, WebP or BMP.'),
      ).toBeInTheDocument(),
    )
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('rejects oversized files without calling the API', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    uploadFile(pngFile('huge.png', 9_000_000))

    await waitFor(() => expect(screen.getByText(/File too large/)).toBeInTheDocument())
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('surfaces a short message when the API is unreachable', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('failed to fetch')
      }),
    )
    render(<App />)
    uploadFile(pngFile())

    await waitFor(() =>
      expect(
        screen.getByText('Cannot reach the analysis service — check it is running.'),
      ).toBeInTheDocument(),
    )
  })

  it('surfaces backend validation errors', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse({ code: 'corrupt_image', message: 'Image file is corrupt or incomplete.' }, 400),
      ),
    )
    render(<App />)
    uploadFile(pngFile())

    await waitFor(() =>
      expect(screen.getByText('Image file is corrupt or incomplete.')).toBeInTheDocument(),
    )
  })

  it('shows a pending state and blocks a second submission while analysing', async () => {
    let release: (value: Response) => void = () => {}
    const pending = new Promise<Response>((resolve) => {
      release = resolve
    })
    const fetchMock = vi.fn(() => pending)
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    uploadFile(pngFile())
    await waitFor(() => expect(screen.getByText('Analysing image…')).toBeInTheDocument())

    uploadFile(pngFile('second.png'))
    expect(fetchMock).toHaveBeenCalledTimes(1)

    release(jsonResponse(buildResponse()))
    await waitFor(() => expect(screen.getByText('Pass')).toBeInTheDocument())
  })

  it('reset clears the result and releases the preview object URL', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(buildResponse())))
    render(<App />)
    uploadFile(pngFile())

    await waitFor(() => expect(screen.getByText('Pass')).toBeInTheDocument())
    expect(createObjectURL).toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Reset' }))
    expect(screen.queryByText('Pass')).not.toBeInTheDocument()
    expect(screen.getByText('No image analysed yet.')).toBeInTheDocument()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:preview')
  })
})
