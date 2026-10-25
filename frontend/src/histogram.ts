export interface Bin {
  start: number
  end: number
  count: number
}

/**
 * Count values into fixed-width bins aligned to multiples of `width`.
 * Each bin is [start, end); empty bins between the min and max are kept so the
 * chart has no gaps.
 */
export function binValues(values: number[], width: number): Bin[] {
  if (width <= 0) throw new Error('width must be positive')
  const finite = values.filter(Number.isFinite)
  if (finite.length === 0) return []

  const first = Math.floor(Math.min(...finite) / width)
  const last = Math.floor(Math.max(...finite) / width)
  const bins: Bin[] = []
  for (let i = first; i <= last; i++) {
    bins.push({ start: i * width, end: (i + 1) * width, count: 0 })
  }
  for (const v of finite) {
    bins[Math.floor(v / width) - first].count++
  }
  return bins
}
