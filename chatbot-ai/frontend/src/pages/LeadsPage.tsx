import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Archive,
  ArchiveRestore,
  Building2,
  ChevronLeft,
  ChevronRight,
  Eye,
  Mail,
  MessageCircle,
  Phone,
  RefreshCw,
  Search,
  Trash2,
} from 'lucide-react'
import { leadsApi } from '../api/resources'
import { apiErrorMessage } from '../api/client'
import type { Lead, LeadStatus } from '../api/types'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'
import { ErrorBanner, LoadingSpinner, EmptyState } from '../components/ui/Feedback'
import { useToast } from '../components/ui/Toast'
import { WhatsAppPreviewModal } from '../components/leads/WhatsAppPreviewModal'

const PAGE_SIZE = 10

const STATUS_TABS: { value: LeadStatus | ''; label: string }[] = [
  { value: '', label: 'All' },
  { value: 'new', label: 'New' },
  { value: 'contacted', label: 'Contacted' },
  { value: 'qualified', label: 'Qualified' },
  { value: 'converted', label: 'Converted' },
  { value: 'closed', label: 'Closed' },
]

// Same soft tint each status gets from Badge.tsx, just used as the tab's
// own background so the status is legible before you even read the label.
const STATUS_TAB_COLORS: Record<LeadStatus | '', { soft: string; active: string }> = {
  '': { soft: 'text-slate-600 hover:bg-slate-200/70', active: 'bg-white text-slate-900 shadow-sm' },
  new: { soft: 'text-accent-700 hover:bg-accent-100', active: 'bg-accent-100 text-accent-700 shadow-sm ring-1 ring-accent-200' },
  contacted: { soft: 'text-amber-700 hover:bg-amber-100', active: 'bg-amber-100 text-amber-700 shadow-sm ring-1 ring-amber-200' },
  qualified: { soft: 'text-brand-700 hover:bg-brand-100', active: 'bg-brand-100 text-brand-700 shadow-sm ring-1 ring-brand-200' },
  converted: {
    soft: 'text-emerald-700 hover:bg-emerald-100',
    active: 'bg-emerald-100 text-emerald-700 shadow-sm ring-1 ring-emerald-200',
  },
  closed: { soft: 'text-slate-600 hover:bg-slate-200/70', active: 'bg-slate-200 text-slate-700 shadow-sm' },
}

const STATUS_OPTIONS: LeadStatus[] = ['new', 'contacted', 'qualified', 'converted', 'closed']

const EMPTY_STATUS_COUNTS: Record<LeadStatus, number> = {
  new: 0,
  contacted: 0,
  qualified: 0,
  converted: 0,
  closed: 0,
}

const AVATAR_COLORS = [
  'bg-brand-100 text-brand-700',
  'bg-accent-100 text-accent-700',
  'bg-emerald-100 text-emerald-700',
  'bg-amber-100 text-amber-700',
  'bg-rose-100 text-rose-700',
]

function initials(name: string | null): string {
  if (!name) return '?'
  const parts = name.trim().split(/\s+/)
  return ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase() || '?'
}

function avatarColor(seed: string): string {
  let hash = 0
  for (let i = 0; i < seed.length; i++) hash = (hash * 31 + seed.charCodeAt(i)) >>> 0
  return AVATAR_COLORS[hash % AVATAR_COLORS.length]
}

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime()
  const min = Math.floor(diffMs / 60000)
  if (min < 1) return 'just now'
  if (min < 60) return `${min}m ago`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}h ago`
  const days = Math.floor(hr / 24)
  if (days < 7) return `${days}d ago`
  return new Date(iso).toLocaleDateString()
}

export function LeadsPage() {
  const { notify } = useToast()
  const [view, setView] = useState<'active' | 'archived'>('active')
  const [leads, setLeads] = useState<Lead[]>([])
  const [total, setTotal] = useState(0)
  const [statusCounts, setStatusCounts] = useState<Record<LeadStatus, number>>(EMPTY_STATUS_COUNTS)
  const [statusFilter, setStatusFilter] = useState<LeadStatus | ''>('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Lead | null>(null)
  const [whatsappTarget, setWhatsappTarget] = useState<Lead | null>(null)

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const grandTotal = useMemo(() => Object.values(statusCounts).reduce((sum, n) => sum + n, 0), [statusCounts])

  async function load(isManualRefresh = false) {
    if (isManualRefresh) setRefreshing(true)
    else setLoading(true)
    setError(null)
    try {
      const { data } = await leadsApi.list({
        status: statusFilter || undefined,
        archived: view === 'archived',
        page,
        page_size: PAGE_SIZE,
      })
      setLeads(data.items)
      setTotal(data.total)
      setStatusCounts(data.status_counts)
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, view, page])

  useEffect(() => {
    setPage(1)
  }, [statusFilter, view])

  const filtered = useMemo(() => {
    if (!search.trim()) return leads
    const q = search.trim().toLowerCase()
    return leads.filter((l) => [l.name, l.email, l.phone, l.company].some((v) => v?.toLowerCase().includes(q)))
  }, [leads, search])

  async function handleStatusChange(lead: Lead, status: LeadStatus) {
    try {
      await leadsApi.update(lead.id, { status })
      setLeads((prev) => prev.map((l) => (l.id === lead.id ? { ...l, status } : l)))
    } catch (err) {
      notify(apiErrorMessage(err), 'error')
    }
  }

  async function handleArchive(lead: Lead) {
    try {
      await leadsApi.archive(lead.id)
      setLeads((prev) => prev.filter((l) => l.id !== lead.id))
      setTotal((t) => t - 1)
      notify('Lead archived')
    } catch (err) {
      notify(apiErrorMessage(err), 'error')
    }
  }

  async function handleUnarchive(lead: Lead) {
    try {
      await leadsApi.unarchive(lead.id)
      setLeads((prev) => prev.filter((l) => l.id !== lead.id))
      setTotal((t) => t - 1)
      notify('Lead moved back to leads')
    } catch (err) {
      notify(apiErrorMessage(err), 'error')
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return
    try {
      await leadsApi.remove(deleteTarget.id)
      setLeads((prev) => prev.filter((l) => l.id !== deleteTarget.id))
      setTotal((t) => t - 1)
      notify('Lead deleted')
      setDeleteTarget(null)
    } catch (err) {
      notify(apiErrorMessage(err), 'error')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-slate-900">Leads</h1>
          <p className="mt-0.5 text-sm text-slate-500">
            {total} {view === 'archived' ? 'archived ' : ''}lead{total === 1 ? '' : 's'}
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          <div className="flex gap-1 rounded-lg border border-slate-200 bg-slate-50 p-1">
            <button
              onClick={() => setView('active')}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                view === 'active' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              Leads
            </button>
            <button
              onClick={() => setView('archived')}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                view === 'archived' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              Archived
            </button>
          </div>
          <Button variant="secondary" onClick={() => load(true)}>
            <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      <div className="space-y-3">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            placeholder="Search by name, email, phone, or company…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2.5 pl-10 pr-3 text-sm transition-colors hover:border-slate-300 focus:border-brand-500 focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        </div>

        <div className="flex flex-wrap gap-1.5 rounded-xl bg-slate-100 p-1">
          {STATUS_TABS.map((tab) => {
            const colors = STATUS_TAB_COLORS[tab.value]
            return (
              <button
                key={tab.value}
                onClick={() => setStatusFilter(tab.value)}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
                  statusFilter === tab.value ? colors.active : colors.soft
                }`}
              >
                {tab.label}{' '}
                <span className={statusFilter === tab.value ? 'opacity-70' : 'opacity-60'}>
                  {tab.value === '' ? grandTotal : statusCounts[tab.value]}
                </span>
              </button>
            )
          })}
        </div>
      </div>

      {error && <ErrorBanner message={error} />}
      {loading && <LoadingSpinner />}

      {!loading && !error && filtered.length === 0 && (
        <EmptyState
          title={view === 'archived' ? 'No archived leads' : 'No leads found'}
          description={search ? 'Try a different search term.' : 'Leads will show up here once visitors show buying intent.'}
        />
      )}

      {!loading && filtered.length > 0 && (
        <>
          <ul className="space-y-2.5">
            {filtered.map((lead) => (
              <li
                key={lead.id}
                className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 transition-all hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md hover:shadow-slate-900/5 sm:flex-row sm:items-center"
              >
                <div
                  className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${avatarColor(lead.id)}`}
                >
                  {initials(lead.name)}
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-slate-900">{lead.name ?? 'Anonymous'}</span>
                    <Badge status={lead.source} />
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
                    {lead.email && (
                      <span className="inline-flex items-center gap-1">
                        <Mail className="h-3 w-3 text-slate-400" />
                        {lead.email}
                      </span>
                    )}
                    {lead.phone && (
                      <span className="inline-flex items-center gap-1">
                        <Phone className="h-3 w-3 text-slate-400" />
                        {lead.phone}
                      </span>
                    )}
                    {lead.company && (
                      <span className="inline-flex items-center gap-1">
                        <Building2 className="h-3 w-3 text-slate-400" />
                        {lead.company}
                      </span>
                    )}
                    <span>{timeAgo(lead.created_at)}</span>
                  </div>
                </div>

                <div className="flex shrink-0 flex-wrap items-center gap-3 sm:justify-end">
                  <select
                    value={lead.status}
                    onChange={(e) => handleStatusChange(lead, e.target.value as LeadStatus)}
                    className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs font-medium capitalize transition-colors hover:border-slate-300 focus:border-brand-500 focus:bg-white focus:outline-none"
                  >
                    {STATUS_OPTIONS.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>

                  <div className="flex items-center gap-2 border-l border-slate-200 pl-3">
                    <button
                      title="WhatsApp AI preview"
                      className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 transition-colors hover:bg-emerald-100"
                      onClick={() => setWhatsappTarget(lead)}
                    >
                      <MessageCircle className="h-4 w-4" />
                    </button>
                    <Link
                      to={`/conversations/${lead.conversation_id}`}
                      title="View conversation"
                      className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-50 text-brand-600 transition-colors hover:bg-brand-100"
                    >
                      <Eye className="h-4 w-4" />
                    </Link>
                    {view === 'active' ? (
                      <button
                        title="Archive"
                        className="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-100 text-slate-600 transition-colors hover:bg-slate-200"
                        onClick={() => handleArchive(lead)}
                      >
                        <Archive className="h-4 w-4" />
                      </button>
                    ) : (
                      <>
                        <button
                          title="Unarchive"
                          className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 transition-colors hover:bg-emerald-100"
                          onClick={() => handleUnarchive(lead)}
                        >
                          <ArchiveRestore className="h-4 w-4" />
                        </button>
                        <button
                          title="Delete"
                          className="flex h-7 w-7 items-center justify-center rounded-lg bg-red-50 text-red-600 transition-colors hover:bg-red-100"
                          onClick={() => setDeleteTarget(lead)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>

          {totalPages > 1 && (
            <div className="flex items-center justify-between rounded-2xl border border-slate-200 bg-white px-5 py-3">
              <span className="text-xs text-slate-500">
                Page <span className="font-medium text-slate-700">{page}</span> of{' '}
                <span className="font-medium text-slate-700">{totalPages}</span>
              </span>
              <div className="flex items-center gap-2">
                <Button variant="secondary" className="px-3 py-1.5" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
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
        </>
      )}

      {deleteTarget && (
        <ConfirmDialog
          title="Delete lead"
          message={`Permanently delete the lead for ${deleteTarget.name ?? deleteTarget.email ?? 'this visitor'}? This cannot be undone.`}
          confirmLabel="Delete"
          danger
          onConfirm={handleDelete}
          onCancel={() => setDeleteTarget(null)}
        />
      )}

      {whatsappTarget && <WhatsAppPreviewModal lead={whatsappTarget} onClose={() => setWhatsappTarget(null)} />}
    </div>
  )
}
