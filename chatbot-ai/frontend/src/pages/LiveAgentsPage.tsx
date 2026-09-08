import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { liveAgentsApi } from '../api/resources'
import { apiErrorMessage } from '../api/client'
import type { LiveAgentRequest } from '../api/types'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { ErrorBanner, LoadingSpinner, EmptyState } from '../components/ui/Feedback'
import { useToast } from '../components/ui/Toast'

export function LiveAgentsPage() {
  const { notify } = useToast()
  const [requests, setRequests] = useState<LiveAgentRequest[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const { data } = await liveAgentsApi.list()
      setRequests(data)
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }
  

  useEffect(() => {
    load()
  }, [])

  async function handleAssign(id: string) {
    try {
      await liveAgentsApi.assign(id)
      notify('Request assigned to you')
      load()
    } catch (err) {
      notify(apiErrorMessage(err), 'error')
    }
  }

  async function handleResolve(id: string) {
    try {
      await liveAgentsApi.resolve(id)
      notify('Request resolved')
      load()
    } catch (err) {
      notify(apiErrorMessage(err), 'error')
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">Live Agent Requests</h1>
        <Button variant="secondary" onClick={load}>
          Refresh
        </Button>
      </div>

      {error && <ErrorBanner message={error} />}
      {loading && <LoadingSpinner />}
      {!loading && requests.length === 0 && <EmptyState title="No live agent requests" />}

      {!loading && requests.length > 0 && (
        <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Requested At</th>
                <th className="px-4 py-3">Assigned At</th>
                <th className="px-4 py-3">Conversation</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {requests.map((r) => (
                <tr key={r.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <Badge status={r.status} />
                  </td>
                  <td className="px-4 py-3 text-slate-500">{new Date(r.requested_at).toLocaleString()}</td>
                  <td className="px-4 py-3 text-slate-500">{r.assigned_at ? new Date(r.assigned_at).toLocaleString() : '—'}</td>
                  <td className="px-4 py-3">
                    <Link to={`/conversations/${r.conversation_id}`} className="text-brand-600 hover:underline">
                      View
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-right">
                    {r.status === 'waiting' && (
                      <button className="mr-3 text-brand-600 hover:underline" onClick={() => handleAssign(r.id)}>
                        Assign to me
                      </button>
                    )}
                    {(r.status === 'assigned' || r.status === 'active') && (
                      <button className="text-green-600 hover:underline" onClick={() => handleResolve(r.id)}>
                        Resolve
                      </button>
                    )}
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
