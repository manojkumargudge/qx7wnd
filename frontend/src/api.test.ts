import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api, getJson } from './api'

function mockFetch(impl: (url: string) => Promise<Response>) {
  const fn = vi.fn(impl)
  vi.stubGlobal('fetch', fn)
  return fn
}

afterEach(() => vi.unstubAllGlobals())

describe('api client', () => {
  it('builds a relative URL with query params and returns JSON', async () => {
    const fetchMock = mockFetch(async () => new Response(JSON.stringify({ status: 'ok' }), { status: 200 }))
    await expect(api.day('2026-01-15', '09:30')).resolves.toEqual({ status: 'ok' })
    expect(fetchMock.mock.calls[0][0]).toBe('/api/day?date=2026-01-15&cutoff=09%3A30')
  })

  it('surfaces the API detail message on 4xx', async () => {
    mockFetch(async () => new Response(
      JSON.stringify({ detail: 'date: 2026-02-05 is outside the available delivery range' }),
      { status: 422, statusText: 'Unprocessable Entity' },
    ))
    const err = await getJson('/day').catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err).toMatchObject({ status: 422, message: 'date: 2026-02-05 is outside the available delivery range' })
  })

  it('falls back to the status text when the error body is not JSON', async () => {
    mockFetch(async () => new Response('<html>boom</html>', { status: 500, statusText: 'Internal Server Error' }))
    await expect(getJson('/meta')).rejects.toMatchObject({ status: 500, message: 'Internal Server Error' })
  })

  it('reports network failures as status 0 with a readable message', async () => {
    mockFetch(async () => { throw new TypeError('Failed to fetch') })
    await expect(getJson('/meta')).rejects.toMatchObject({ status: 0, message: expect.stringMatching(/reach the server/) })
  })

  it('lets aborts through unchanged', async () => {
    mockFetch(async () => { throw new DOMException('aborted', 'AbortError') })
    await expect(getJson('/meta')).rejects.toMatchObject({ name: 'AbortError' })
  })
})
