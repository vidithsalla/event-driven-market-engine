import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'

function statusColor(status: string) {
  if (status === 'COMPLETED') return 'text-green-600'
  if (status === 'FAILED') return 'text-red-600'
  return 'text-yellow-600'
}

export default function RunsPage() {
  const { data: runs, isLoading, error } = useQuery({ queryKey: ['runs'], queryFn: api.runs.list })

  if (isLoading) return <p className="p-6 text-gray-500">Loading runs…</p>
  if (error) return <p className="p-6 text-red-500">Failed to load runs.</p>

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold">Simulation Runs</h1>
        <Link
          to="/runs/new"
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
        >
          + New Run
        </Link>
      </div>

      {runs && runs.length === 0 ? (
        <p className="text-gray-500">No runs yet. Create one to get started.</p>
      ) : (
        <div className="overflow-x-auto rounded border border-gray-200">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 text-gray-600 uppercase text-xs">
              <tr>
                <th className="px-4 py-3 text-left">ID</th>
                <th className="px-4 py-3 text-left">Strategy</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-left">Started</th>
                <th className="px-4 py-3 text-left"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {runs?.map((run) => (
                <tr key={run.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">{run.id.slice(0, 8)}</td>
                  <td className="px-4 py-3">{run.strategy_name}</td>
                  <td className={`px-4 py-3 font-medium ${statusColor(run.status)}`}>{run.status}</td>
                  <td className="px-4 py-3 text-gray-500">
                    {run.started_at ? new Date(run.started_at).toLocaleString() : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <Link to={`/runs/${run.id}`} className="text-blue-600 hover:underline">
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
