import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Plus, ChevronLeft, ChevronRight } from 'lucide-react'
import { agentsApi } from '../api/resources'
import { apiErrorMessage } from '../api/client'
import type { Agent, AgentStatus } from '../api/types'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { ErrorBanner, LoadingSpinner, EmptyState } from '../components/ui/Feedback'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'
import { RowActionsMenu } from '../components/ui/RowActionsMenu'
import { useToast } from '../components/ui/Toast'

const PAGE_SIZE = 10

export function AgentsPage() {
  const navigate = useNavigate()
  const { notify } = useToast()
  const [agents, setAgents] = useState<Agent[]>([])
  const [total, setTotal] = useState(0)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<AgentStatus | ''>('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Agent | null>(null)

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const { data } = await agentsApi.list({
        search: search || undefined,
        status: statusFilter || undefined,
        page,
        page_size: PAGE_SIZE,
      })
      setAgents(data.items)
      setTotal(data.total)
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const timer = setTimeout(load, 250)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, statusFilter, page])

  async function handleAction(agent: Agent, action: 'activate' | 'deactivate' | 'duplicate') {
    setMenuOpenId(null)
    try {
      if (action === 'activate') await agentsApi.activate(agent.id)
      if (action === 'deactivate') await agentsApi.deactivate(agent.id)
      if (action === 'duplicate') {
        await agentsApi.duplicate(agent.id)
        notify('Agent duplicated')
      }
      load()
    } catch (err) {
      notify(apiErrorMessage(err), 'error')
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return
    try {
      await agentsApi.remove(deleteTarget.id)
      notify('Agent deleted')
      setDeleteTarget(null)
      load()
    } catch (err) {
      notify(apiErrorMessage(err), 'error')
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">AI Agents</h1>
        <Link to="/agents/new">
          <Button>
            <Plus className="h-4 w-4" />
            Create New Agent
          </Button>
        </Link>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <input
          placeholder="Search by name or company…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(1)
          }}
          className="w-64 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
        />
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value as AgentStatus | '')
            setPage(1)
          }}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
        >
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
        <Button variant="secondary" onClick={load}>
          Refresh
        </Button>
        <span className="text-sm text-slate-500">{total} agent(s)</span>
      </div>

      {error && <ErrorBanner message={error} />}
      {loading && <LoadingSpinner />}

      {!loading && !error && agents.length === 0 && (
        <EmptyState title="No agents yet" description="Create your first AI agent to get started." />
      )}

      {!loading && agents.length > 0 && (
        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50">
                <tr>
                  <th className="px-4 py-3 text-[11px] font-semibold uppercase tracking-wide text-slate-500">Agent Name</th>
                  <th className="px-4 py-3 text-[11px] font-semibold uppercase tracking-wide text-slate-500">Company</th>
                  <th className="px-4 py-3 text-[11px] font-semibold uppercase tracking-wide text-slate-500">Industry</th>
                  <th className="px-4 py-3 text-[11px] font-semibold uppercase tracking-wide text-slate-500">Languages</th>
                  <th className="px-4 py-3 text-[11px] font-semibold uppercase tracking-wide text-slate-500">Status</th>
                  <th className="px-4 py-3 text-[11px] font-semibold uppercase tracking-wide text-slate-500">Created On</th>
                  <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {agents.map((agent) => (
                  <tr key={agent.id} className="transition-colors hover:bg-slate-50">
                    <td className="px-4 py-3 font-medium text-slate-900">
                      <Link to={`/agents/${agent.id}`} className="hover:text-brand-600">
                        {agent.name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-slate-600">{agent.company_name}</td>
                    <td className="px-4 py-3 text-slate-600">{agent.industry ?? '—'}</td>
                    <td className="px-4 py-3">
                      {agent.languages.length === 0 ? (
                        <span className="text-slate-400">—</span>
                      ) : (
                        <div className="flex flex-wrap gap-1">
                          {agent.languages.map((lang) => (
                            <span key={lang} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                              {lang}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <Badge status={agent.status} />
                    </td>
                    <td className="px-4 py-3 text-slate-500">{new Date(agent.created_at).toLocaleDateString()}</td>
                    <td className="px-4 py-3 text-right">
                      <RowActionsMenu
                        open={menuOpenId === agent.id}
                        onToggle={() => setMenuOpenId(menuOpenId === agent.id ? null : agent.id)}
                        onClose={() => setMenuOpenId(null)}
                        actions={[
                          { label: 'View / Edit', onClick: () => navigate(`/agents/${agent.id}`) },
                          { label: 'Duplicate', onClick: () => handleAction(agent, 'duplicate') },
                          agent.status === 'active'
                            ? { label: 'Deactivate', onClick: () => handleAction(agent, 'deactivate') }
                            : { label: 'Activate', onClick: () => handleAction(agent, 'activate') },
                          { label: 'Delete', danger: true, onClick: () => setDeleteTarget(agent) },
                        ]}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50/50 px-4 py-3">
              <span className="text-xs text-slate-500">
                Page <span className="font-medium text-slate-700">{page}</span> of{' '}
                <span className="font-medium text-slate-700">{totalPages}</span>
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  className="px-3 py-1.5"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  <ChevronLeft className="h-4 w-4" />
                  Previous
                </Button>
                <Button
                  variant="secondary"
                  className="px-3 py-1.5"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

      {deleteTarget && (
        <ConfirmDialog
          title="Delete agent"
          message={`Are you sure you want to permanently delete "${deleteTarget.name}"? This cannot be undone.`}
          confirmLabel="Delete"
          danger
          onConfirm={handleDelete}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  )
}
