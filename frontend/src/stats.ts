import type { CorrectionMethod, DailyStat } from './api'

export interface DayComparison {
  better: number
  worse: number
  same: number
  total: number
}

/** Count days where the adjusted forecast's MAE beat, lost to, or tied the published forecast's. */
export function compareDays(daily: DailyStat[], method: CorrectionMethod): DayComparison {
  const key = method === 'additive' ? 'additive_mae' : 'ratio_mae'
  let better = 0
  let worse = 0
  for (const d of daily) {
    if (d[key] < d.mae) better++
    else if (d[key] > d.mae) worse++
  }
  return { better, worse, same: daily.length - better - worse, total: daily.length }
}

/** "beat the published forecast on 21 of 31 days and did worse on 10" */
export function comparisonPhrase(c: DayComparison): string {
  const tie = c.same ? ` (${c.same} tied)` : ''
  return `beat the published forecast on ${c.better} of ${c.total} days and did worse on ${c.worse}${tie}`
}
