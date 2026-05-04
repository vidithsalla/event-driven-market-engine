export interface Run {
  id: string
  strategy_name: string
  status: string
  started_at: string | null
  ended_at: string | null
  config_json: string | null
}

export interface Trade {
  id: string
  run_id: string
  order_id: string
  symbol: string
  side: string
  quantity: number
  fill_price: number
  fee: number
  timestamp: string
}

export interface Order {
  id: string
  run_id: string
  symbol: string
  side: string
  quantity: number
  requested_price: number
  status: string
  rejection_reason: string | null
}

export interface Signal {
  id: string
  run_id: string
  symbol: string
  action: string
  quantity: number
  reason: string | null
  timestamp: string
}

export interface Position {
  id: string
  run_id: string
  symbol: string
  quantity: number
  average_cost: number
  realized_pnl: number
  unrealized_pnl: number
}

export interface PortfolioSnapshot {
  id: string
  run_id: string
  timestamp: string
  cash: number
  equity: number
  gross_exposure: number
  net_exposure: number
  realized_pnl: number
  unrealized_pnl: number
  total_pnl: number
}

export interface Metrics {
  run_id: string
  total_pnl: number
  realized_pnl: number
  unrealized_pnl: number
  max_drawdown: number
  trade_count: number
  win_rate: number
  max_position_value: number
}

export interface Strategy {
  name: string
  description: string
  parameters: string[]
}
