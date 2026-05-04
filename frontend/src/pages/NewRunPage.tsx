import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

export default function NewRunPage() {
  const navigate = useNavigate()
  const { data: strategies } = useQuery({ queryKey: ['strategies'], queryFn: api.strategies })

  const [strategy, setStrategy] = useState('ma_crossover')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const run = await api.runs.create(strategy)
      navigate(`/runs/${run.id}`)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-6 max-w-lg">
      <div className="flex items-center gap-3 mb-6">
        <Link to="/" className="text-blue-600 hover:underline text-sm">← Runs</Link>
        <h1 className="text-2xl font-semibold">New Simulation Run</h1>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Strategy</label>
          <select
            value={strategy}
            onChange={(e) => setStrategy(e.target.value)}
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
          >
            {strategies?.map((s) => (
              <option key={s.name} value={s.name}>
                {s.name}
              </option>
            ))}
          </select>
          <p className="text-xs text-gray-500 mt-1">
            {strategies?.find((s) => s.name === strategy)?.description}
          </p>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm disabled:opacity-50"
        >
          {loading ? 'Running simulation…' : 'Run Simulation'}
        </button>
      </form>

      <div className="mt-6 p-4 bg-gray-50 rounded border border-gray-200 text-xs text-gray-500">
        <p className="font-medium mb-1">Note</p>
        <p>Runs use the sample event stream (47 events, AAPL, MA defaults: short=5, long=20).</p>
      </div>
    </div>
  )
}
