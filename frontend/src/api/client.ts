import type { Metrics, Order, PortfolioSnapshot, Position, Run, Signal, Strategy, Trade } from './types'

const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json()
}

export const api = {
  runs: {
    list: () => get<Run[]>('/runs'),
    get: (id: string) => get<Run>(`/runs/${id}`),
    create: (strategy_name: string, config?: Record<string, unknown>) =>
      post<Run>('/runs', { strategy_name, config: config ?? {} }),
  },
  trades: (runId: string) => get<Trade[]>(`/runs/${runId}/trades`),
  orders: (runId: string) => get<Order[]>(`/runs/${runId}/orders`),
  signals: (runId: string) => get<Signal[]>(`/runs/${runId}/signals`),
  positions: (runId: string) => get<Position[]>(`/runs/${runId}/positions`),
  portfolio: (runId: string) => get<PortfolioSnapshot[]>(`/runs/${runId}/portfolio`),
  metrics: (runId: string) => get<Metrics>(`/runs/${runId}/metrics`),
  strategies: () => get<Strategy[]>('/strategies'),
}
