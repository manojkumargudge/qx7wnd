import { describe, expect, it } from 'vitest'
import { buildGapSeries } from './gapShading'

describe('buildGapSeries', () => {
  it('puts the band on the shortfall side when forecast is above actual', () => {
    const [p] = buildGapSeries([{ hour: 0, forecast: 120, actual: 100 }])
    expect(p.shortfall).toEqual([100, 120])
    expect(p.surplus).toEqual([100, 100])
  })

  it('puts the band on the surplus side when forecast is below actual', () => {
    const [p] = buildGapSeries([{ hour: 0, forecast: 80, actual: 100 }])
    expect(p.surplus).toEqual([80, 100])
    expect(p.shortfall).toEqual([100, 100])
  })

  it('inserts a zero-width point where the lines cross', () => {
    // Gap +20 at hour 0, -20 at hour 1: they cross half way.
    const pts = buildGapSeries([
      { hour: 0, forecast: 120, actual: 100 },
      { hour: 1, forecast: 100, actual: 120 },
    ])
    expect(pts.map((p) => p.hour)).toEqual([0, 0.5, 1])
    const cross = pts[1]
    expect(cross.crossing).toBe(true)
    expect(cross.forecast).toBeCloseTo(110)
    expect(cross.shortfall).toEqual([110, 110])
    expect(cross.surplus).toEqual([110, 110])
  })

  it('does not insert a point when the gap touches zero without crossing', () => {
    const pts = buildGapSeries([
      { hour: 0, forecast: 120, actual: 100 },
      { hour: 1, forecast: 100, actual: 100 },
      { hour: 2, forecast: 130, actual: 100 },
    ])
    expect(pts).toHaveLength(3)
  })

  it('leaves hours without an actual unshaded', () => {
    const pts = buildGapSeries([
      { hour: 0, forecast: 120, actual: 100 },
      { hour: 1, forecast: 90, actual: null },
    ])
    expect(pts[1]).toMatchObject({ shortfall: null, surplus: null, crossing: false })
  })
})
