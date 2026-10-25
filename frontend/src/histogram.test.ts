import { describe, expect, it } from 'vitest'
import { binValues } from './histogram'

describe('binValues', () => {
  it('counts values into [start, end) bins aligned to the width', () => {
    expect(binValues([-600, -10, 0, 499, 500, 1200], 500)).toEqual([
      { start: -1000, end: -500, count: 1 },
      { start: -500, end: 0, count: 1 },
      { start: 0, end: 500, count: 2 },
      { start: 500, end: 1000, count: 1 },
      { start: 1000, end: 1500, count: 1 },
    ])
  })

  it('keeps empty bins between the extremes', () => {
    const bins = binValues([0, 2100], 500)
    expect(bins.map((b) => b.count)).toEqual([1, 0, 0, 0, 1])
  })

  it('ignores non-finite values and handles empty input', () => {
    expect(binValues([], 500)).toEqual([])
    expect(binValues([Number.NaN, Infinity], 500)).toEqual([])
    expect(binValues([NaN, 10], 500)).toEqual([{ start: 0, end: 500, count: 1 }])
  })

  it('rejects a non-positive width', () => {
    expect(() => binValues([1], 0)).toThrow('width must be positive')
  })

  it('preserves the total count', () => {
    const values = Array.from({ length: 744 }, (_, i) => Math.sin(i) * 4000 + 1500)
    expect(binValues(values, 500).reduce((n, b) => n + b.count, 0)).toBe(744)
  })
})
