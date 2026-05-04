import { useQuery } from '@tanstack/react-query'
import { useParams, Link } from 'react-router-dom'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { api } from '../api/client'

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white border border-gray-200 rounded p-4">
      <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">{label}</p>
      <p className="text-xl font-semibold">{value}</p>
    </div>
  )
}

function fmt(n: number) {
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>()

  const { data: run } = useQuery({ queryKey: ['run', runId], queryFn: () => api.runs.get(runId!) })
  const { data: metrics } = useQuery({ queryKey: ['metrics', runId], queryFn: () => api.metrics(runId!) })
  const { data: snapshots } = useQuery({ queryKey: ['portfolio', runId], queryFn: () => api.portfolio(runId!) })
  const { data: trades } = useQuery({ queryKey: ['trades', runId], queryFn: () => api.trades(runId!) })
  const { data: positions } = useQuery({ queryKey: ['positions', runId], queryFn: () => api.positions(runId!) })
  const { data: orders } = useQuery({ queryKey: ['orders', runId], queryFn: () => api.orders(runId!) })

  const chartData = (snapshots ?? []).map((s, i) => ({
    i,
    pnl: s.total_pnl,
    equity: s.equity,
  }))

  const rejected = (orders ?? []).filter((o) => o.status === 'REJECTED_RISK')

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <Link to="/" className="text-blue-600 hover:underline text-sm">← Runs</Link>
        <h1 className="text-2xl font-semibold">
          {run?.strategy_name ?? 'Run'}{' '}
          <span className="text-gray-400 text-base font-mono">{runId?.slice(0, 8)}</span>
        </h1>
      </div>

      {/* Metrics */}
      {metrics && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard label="Total PnL" value={`$${fmt(metrics.total_pnl)}`} />
          <MetricCard label="Realized PnL" value={`$${fmt(metrics.realized_pnl)}`} />
          <MetricCard label="Unrealized PnL" value={`$${fmt(metrics.unrealized_pnl)}`} />
          <MetricCard label="Trades" value={String(metrics.trade_count)} />
        </div>
      )}

      {/* PnL chart */}
      {chartData.length > 0 && (
        <div className="bg-white border border-gray-200 rounded p-4">
          <h2 className="text-sm font-medium text-gray-700 mb-3">Portfolio PnL Over Events</h2>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="i" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => [`$${fmt(Number(v))}`, 'PnL']} />
              <Line type="monotone" dataKey="pnl" stroke="#2563eb" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Positions */}
      {positions && positions.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-gray-700 mb-2">Positions</h2>
          <div className="overflow-x-auto rounded border border-gray-200">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-gray-500 uppercase text-xs">
                <tr>
                  <th className="px-4 py-2 text-left">Symbol</th>
                  <th className="px-4 py-2 text-right">Qty</th>
                  <th className="px-4 py-2 text-right">Avg Cost</th>
                  <th className="px-4 py-2 text-right">Realized PnL</th>
                  <th className="px-4 py-2 text-right">Unrealized PnL</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {positions.map((p) => (
                  <tr key={p.id}>
                    <td className="px-4 py-2 font-medium">{p.symbol}</td>
                    <td className="px-4 py-2 text-right">{p.quantity}</td>
                    <td className="px-4 py-2 text-right">${fmt(p.average_cost)}</td>
                    <td className={`px-4 py-2 text-right ${p.realized_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      ${fmt(p.realized_pnl)}
                    </td>
                    <td className={`px-4 py-2 text-right ${p.unrealized_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      ${fmt(p.unrealized_pnl)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Trades */}
      {trades && trades.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-gray-700 mb-2">Trades</h2>
          <div className="overflow-x-auto rounded border border-gray-200">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-gray-500 uppercase text-xs">
                <tr>
                  <th className="px-4 py-2 text-left">Time</th>
                  <th className="px-4 py-2 text-left">Symbol</th>
                  <th className="px-4 py-2 text-left">Side</th>
                  <th className="px-4 py-2 text-right">Qty</th>
                  <th className="px-4 py-2 text-right">Fill Price</th>
                  <th className="px-4 py-2 text-right">Fee</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {trades.map((t) => (
                  <tr key={t.id}>
                    <td className="px-4 py-2 text-gray-500 text-xs">{new Date(t.timestamp).toLocaleString()}</td>
                    <td className="px-4 py-2">{t.symbol}</td>
                    <td className={`px-4 py-2 font-medium ${t.side === 'BUY' ? 'text-green-600' : 'text-red-600'}`}>
                      {t.side}
                    </td>
                    <td className="px-4 py-2 text-right">{t.quantity}</td>
                    <td className="px-4 py-2 text-right">${fmt(t.fill_price)}</td>
                    <td className="px-4 py-2 text-right text-gray-500">${fmt(t.fee)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Rejected Orders */}
      {rejected.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-gray-700 mb-2">Rejected Orders ({rejected.length})</h2>
          <div className="overflow-x-auto rounded border border-gray-200">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-gray-500 uppercase text-xs">
                <tr>
                  <th className="px-4 py-2 text-left">Symbol</th>
                  <th className="px-4 py-2 text-left">Side</th>
                  <th className="px-4 py-2 text-right">Qty</th>
                  <th className="px-4 py-2 text-left">Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {rejected.map((o) => (
                  <tr key={o.id}>
                    <td className="px-4 py-2">{o.symbol}</td>
                    <td className="px-4 py-2">{o.side}</td>
                    <td className="px-4 py-2 text-right">{o.quantity}</td>
                    <td className="px-4 py-2 text-red-600 text-xs">{o.rejection_reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
