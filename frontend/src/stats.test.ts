import { describe, expect, it } from 'vitest'
import type { DailyStat } from './api'
import { compareDays, comparisonPhrase } from './stats'

const day = (mae: number, additive_mae: number, ratio_mae: number): DailyStat =>
  ({ date: '2026-01-02', mae, bias: 0, additive_mae, ratio_mae })

describe('compareDays', () => {
  const daily = [day(100, 90, 120), day(100, 110, 80), day(100, 100, 50), day(200, 150, 250)]

  it('counts better, worse and tied days per method', () => {
    expect(compareDays(daily, 'additive')).toEqual({ better: 2, worse: 1, same: 1, total: 4 })
    expect(compareDays(daily, 'ratio')).toEqual({ better: 2, worse: 2, same: 0, total: 4 })
  })

  it('handles an empty series', () => {
    expect(compareDays([], 'ratio')).toEqual({ better: 0, worse: 0, same: 0, total: 0 })
  })

  it('words the result, mentioning ties only when there are some', () => {
    expect(comparisonPhrase({ better: 21, worse: 10, same: 0, total: 31 }))
      .toBe('beat the published forecast on 21 of 31 days and did worse on 10')
    expect(comparisonPhrase({ better: 2, worse: 1, same: 1, total: 4 }))
      .toBe('beat the published forecast on 2 of 4 days and did worse on 1 (1 tied)')
  })
})
