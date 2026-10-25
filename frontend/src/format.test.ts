import { describe, expect, it } from 'vitest'
import {
  biasSentence, formatGWh, formatHours, formatK, formatMW, formatPublish, formatSignedMW, leadRange, p10Sentence, p90Sentence,
} from './format'

describe('KPI formatting', () => {
  it('formats MW with thousands separators and no decimals', () => {
    expect(formatMW(1041.8)).toBe('1,042 MW')
    expect(formatMW(12345.4)).toBe('12,345 MW')
    expect(formatMW(-549.3)).toBe('−549 MW')
    expect(formatMW(-0.4)).toBe('0 MW')
    expect(formatMW(null)).toBe('–')
  })

  it('formats energy in GWh with one decimal and thousands separators', () => {
    expect(formatGWh(25004)).toBe('25.0 GWh')
    expect(formatGWh(17263.7)).toBe('17.3 GWh')
    expect(formatGWh(1408689.5)).toBe('1,408.7 GWh')
    expect(formatGWh(0)).toBe('0.0 GWh')
    expect(formatGWh(-0)).toBe('0.0 GWh')
    expect(formatGWh(null)).toBe('–')
  })

  it('formats axis ticks in thousands without hiding half steps', () => {
    expect(formatK(18000)).toBe('18k')
    expect(formatK(4500)).toBe('4.5k')
    expect(formatK(13500)).toBe('13.5k')
    expect(formatK(-2000)).toBe('−2k')
    expect(formatK(0)).toBe('0k')
  })

  it('adds an explicit sign for bias-style values', () => {
    expect(formatSignedMW(1747.9)).toBe('+1,748 MW')
    expect(formatSignedMW(-2297.7)).toBe('−2,298 MW')
    expect(formatSignedMW(0.3)).toBe('0 MW')
  })

  it('describes bias in plain words with the right direction', () => {
    expect(biasSentence(1041.8)).toBe('Forecast was too high by 1,042 MW on average')
    expect(biasSentence(-671.2)).toBe('Forecast was too low by 671 MW on average')
    expect(biasSentence(0.2)).toBe('Forecast was right on average')
  })

  it('words the P90 and P10 tails by sign', () => {
    expect(p90Sentence(4097.9)).toBe('In 1 of 10 hours, wind came in at least 4,098 MW below forecast.')
    expect(p10Sentence(-549.3)).toBe('In 1 of 10 hours, wind came in at least 549 MW above forecast.')
    expect(p10Sentence(120)).toBe('In 9 of 10 hours the forecast was too high by at least 120 MW.')
  })

  it('formats the publish time and lead range for the info line', () => {
    expect(formatPublish('2026-01-14T07:30:00Z')).toBe('07:30 on 14 Jan')
    const [from, to] = leadRange('2026-01-14T07:30:00Z', '2026-01-15')
    expect([formatHours(from), formatHours(to)]).toEqual(['16.5', '39.5'])
  })
})
