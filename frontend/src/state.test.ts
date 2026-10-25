import { describe, expect, it } from 'vitest'
import { parseUrlState, shiftDate, toSearch, urlNotices } from './state'

describe('URL state', () => {
  it('round-trips tab, date, cutoff and the adjusted toggle', () => {
    const s = { tab: 'accuracy' as const, date: '2026-01-20', cutoff: '09:30', adjusted: true, others: true }
    expect(parseUrlState(toSearch(s))).toEqual(s)
  })

  it('falls back to defaults for invalid or out-of-range values', () => {
    expect(parseUrlState('?tab=nope&date=2026-03-01&cutoff=09:15')).toEqual({
      tab: 'day', date: '2026-01-15', cutoff: '09:00', adjusted: false, others: false,
    })
  })

  it('explains replaced URL values instead of switching silently', () => {
    expect(urlNotices('?date=2026-03-01')).toEqual(['2026-03-01 is outside the data range; showing 15 Jan'])
    expect(urlNotices('?date=yesterday&cutoff=09:15')).toEqual([
      'yesterday is not a valid date; showing 15 Jan',
      '09:15 is not an available deadline; showing 09:00',
    ])
    expect(urlNotices('?tab=day&date=2026-01-20&cutoff=09:30')).toEqual([])
    expect(urlNotices('')).toEqual([])
  })

  it('shifts dates across month ends', () => {
    expect(shiftDate('2026-01-31', 1)).toBe('2026-02-01')
    expect(shiftDate('2026-01-02', -1)).toBe('2026-01-01')
  })
})
