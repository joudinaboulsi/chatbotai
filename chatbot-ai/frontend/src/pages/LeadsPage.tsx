import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { leadsApi } from '../api/resources'
import { apiErrorMessage } from '../api/client'
import type { Lead, LeadStatus } from '../api/types'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { ErrorBanner, LoadingSpinner, EmptyState } from '../components/ui/Feedback'
import { useToast } from '../components/ui/Toast'

const STATUS_OPTIONS: LeadStatus[] = ['new', 'contacted', 'qualified', 'converted', 'closed']

export function LeadsPage() {
  const { notify } = useToast()
  const [leads, setLeads] = useState<Lead[]>([])
  const [total, setTotal] = useState(0)
  const [statusFilter, setStatusFilter] = useState<LeadStatus | ''>('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const { data } = await leadsApi.list({ status: statusFilter || undefined, page: 1, page_size: 50 })
      setLeads(data.items)
      setTotal(data.total)
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter])

  async function handleStatusChange(lead: Lead, status: LeadStatus) {
    try {
      await leadsApi.update(lead.id, { status })
      setLeads((prev) => prev.map((l) => (l.id === lead.id ? { ...l, status } : l)))
    } catch (err) {
      notify(apiErrorMessage(err), 'error')
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">Leads</h1>
        <span className="text-sm text-slate-500">{total} lead(s)</span>
      </div>

      <div className="flex items-center gap-3">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as LeadStatus | '')}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
        >
          <option value="">All statuses</option>
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <Button variant="secondary" onClick={load}>
          Refresh
        </Button>
      </div>

      {error && <ErrorBanner message={error} />}
      {loading && <LoadingSpinner />}
      {!loading && leads.length === 0 && <EmptyState title="No leads yet" />}

      {!loading && leads.length > 0 && (
        <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Email</th>
                <th className="px-4 py-3">Phone</th>
                <th className="px-4 py-3">Source</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Created</th>
                <th className="px-4 py-3">Conversation</th>
              </tr>
            </thead>
            <tbody>
              {leads.map((lead) => (
                <tr key={lead.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-slate-900">{lead.name ?? '—'}</td>
                  <td className="px-4 py-3 text-slate-600">{lead.email ?? '—'}</td>
                  <td className="px-4 py-3 text-slate-600">{lead.phone ?? '—'}</td>
                  <td className="px-4 py-3">
                    <Badge status={lead.source} />
                  </td>
                  <td className="px-4 py-3">
                    <select
                      value={lead.status}
                      onChange={(e) => handleStatusChange(lead, e.target.value as LeadStatus)}
                      className="rounded-lg border border-slate-300 px-2 py-1 text-xs"
                    >
                      {STATUS_OPTIONS.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-4 py-3 text-slate-500">{new Date(lead.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-3">
                    <Link to={`/conversations/${lead.conversation_id}`} className="text-brand-600 hover:underline">
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
