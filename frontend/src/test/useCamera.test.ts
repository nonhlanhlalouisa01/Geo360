import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useCamera } from '../useCamera'

function fakeStream(stop = vi.fn()): MediaStream {
  return { getTracks: () => [{ stop }] } as unknown as MediaStream
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('useCamera', () => {
  it('reports a short message when permission is denied', async () => {
    vi.stubGlobal('navigator', {
      mediaDevices: {
        getUserMedia: vi.fn(async () => {
          throw new DOMException('denied', 'NotAllowedError')
        }),
      },
    })

    const { result } = renderHook(() => useCamera())
    await act(async () => {
      await result.current.start()
    })

    expect(result.current.status).toBe('error')
    expect(result.current.error).toBe('Camera permission denied — allow access or upload a photo.')
  })

  it('reports a short message when no camera is present', async () => {
    vi.stubGlobal('navigator', {
      mediaDevices: {
        getUserMedia: vi.fn(async () => {
          throw new DOMException('none', 'NotFoundError')
        }),
      },
    })

    const { result } = renderHook(() => useCamera())
    await act(async () => {
      await result.current.start()
    })

    expect(result.current.error).toBe('No camera found — upload a photo instead.')
  })

  it('refuses to start in an insecure context', async () => {
    const getUserMedia = vi.fn()
    vi.stubGlobal('isSecureContext', false)
    vi.stubGlobal('navigator', { mediaDevices: { getUserMedia } })

    const { result } = renderHook(() => useCamera())
    await act(async () => {
      await result.current.start()
    })

    expect(result.current.error).toBe('Camera needs HTTPS or localhost — upload a photo instead.')
    expect(getUserMedia).not.toHaveBeenCalled()
  })

  it('stops every media track on stop()', async () => {
    const stop = vi.fn()
    vi.stubGlobal('navigator', {
      mediaDevices: { getUserMedia: vi.fn(async () => fakeStream(stop)) },
    })

    const { result } = renderHook(() => useCamera())
    await act(async () => {
      await result.current.start()
    })
    expect(result.current.status).toBe('active')

    act(() => result.current.stop())
    expect(stop).toHaveBeenCalledTimes(1)
    expect(result.current.status).toBe('idle')
  })

  it('stops every media track on unmount', async () => {
    const stop = vi.fn()
    vi.stubGlobal('navigator', {
      mediaDevices: { getUserMedia: vi.fn(async () => fakeStream(stop)) },
    })

    const { result, unmount } = renderHook(() => useCamera())
    await act(async () => {
      await result.current.start()
    })

    unmount()
    expect(stop).toHaveBeenCalledTimes(1)
  })

  it('fails clearly when capture is attempted without a running camera', async () => {
    const { result } = renderHook(() => useCamera())
    await expect(result.current.capture()).rejects.toThrow('Camera is not running.')
  })
})
