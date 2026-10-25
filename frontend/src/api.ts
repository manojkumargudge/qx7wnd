// Relative base so the same build works behind the Vite proxy and on Vercel.
const API_BASE = '/api'

export interface Health {
  status: string
}

export interface Meta {
  delivery_start: string
  delivery_end: string
  default_cutoff: string
  publish_times_of_day: string[]
  correction_methods: string[]
  default_correction_method: string
  correction_note: string
  data_source: string
  timezone: string
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail ?? detail
    } catch {
      // Body was not JSON; keep the status text.
    }
    throw new Error(`${res.status} ${detail}`)
  }
  return res.json() as Promise<T>
}

export const getHealth = () => getJson<Health>('/health')
export const getMeta = () => getJson<Meta>('/meta')
