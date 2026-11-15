import type { Checkin, Scenario, SpaceWeather } from './types'

export const API_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')
export const WS_URL = API_URL.replace(/^http/, 'ws') + '/ws'

async function request<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(API_URL + path, body === undefined ? undefined : {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${path} returned ${res.status}`)
  return res.json() as Promise<T>
}

export const api = {
  scenarios: () => request<Scenario[]>('/api/scenarios'),
  setScenario: (id: string) => request<{ ok: boolean; scenario: string }>('/api/scenario', { id }),
  checkins: () => request<Checkin[]>('/api/checkins'),
  postCheckin: (mood: number, sleep_hours: number, note: string) =>
    request<Checkin>('/api/checkin', { mood, sleep_hours, note }),
  spaceWeather: () => request<SpaceWeather>('/api/spaceweather'),
}
