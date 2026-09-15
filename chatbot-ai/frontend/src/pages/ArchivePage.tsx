import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArchiveRestore, Mail, MessageCircle, Phone, Quote, RefreshCw, Trash2 } from 'lucide-react'
import { conversationsApi, leadsApi } from '../api/resources'
import { apiErrorMessage } from '../api/client'
import type { ConversationListItem, Lead } from '../api/types'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'
import { ErrorBanner, LoadingSpinner, EmptyState } from '../components/ui/Feedback'
import { useToast } from '../components/ui/Toast'

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

function timeAgo(iso: string | null): string {
  if (!iso) return '—'
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

function ArchivedConversations() {
  const { notify } = useToast()
  const [conversations, setConversations] = useState<ConversationListItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<ConversationListItem | null>(null)

  async function load(isManualRefresh = false) {
    if (isManualRefresh) setRefreshing(true)
    else setLoading(true)
    setError(null)
    try {
      const { data } = await conversationsApi.list({ archived: true, page: 1, page_size: 50 })
      setConversations(data.items)
      setTotal(data.total)
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
  }, [])

  async function handleUnarchive(conversation: ConversationListItem) {
    try {
      await conversationsApi.unarchive(conversation.id)
      setConversations((prev) => prev.filter((c) => c.id !== conversation.id))
      setTotal((t) => t - 1)
      notify('Conversation moved back to Conversations')
    } catch (err) {
      notify(apiErrorMessage(err), 'error')
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return
    try {
      await conversationsApi.remove(deleteTarget.id)
      setConversations((prev) => prev.filter((c) => c.id !== deleteTarget.id))
      setTotal((t) => t - 1)
      notify('Conversation deleted')
      setDeleteTarget(null)
    } catch (err) {
      notify(apiErrorMessage(err), 'error')
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-sm text-slate-500">
          {total} archived conversation{total === 1 ? '' : 's'}
        </span>
        <Button variant="secondary" onClick={() => load(true)}>
          <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {error && <ErrorBanner message={error} />}
      {loading && <LoadingSpinner />}

      {!loading && !error && conversations.length === 0 && (
        <EmptyState title="Nothing archived" description="Conversations you archive will show up here." />
      )}

      {!loading && conversations.length > 0 && (
        <ul className="space-y-2.5">
          {conversations.map((c) => (
            <li key={c.id} className="flex items-start gap-4 rounded-2xl border border-slate-200 bg-white p-4">
              <div className="shrink-0">
                <div
                  className={`flex h-11 w-11 items-center justify-center rounded-full text-sm font-semibold ${avatarColor(c.id)}`}
                >
                  {initials(c.visitor_name)}
                </div>
              </div>

              <Link to={`/conversations/${c.id}`} className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="truncate font-semibold text-slate-900">{c.visitor_name ?? 'Anonymous'}</span>
                    <Badge status={c.status} />
                  </div>
                  <span className="shrink-0 text-xs text-slate-400">{timeAgo(c.archived_at)}</span>
                </div>

                <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
                  {c.visitor_phone && (
                    <span className="inline-flex items-center gap-1">
                      <Phone className="h-3 w-3 text-slate-400" />
                      {c.visitor_phone}
                    </span>
                  )}
                  <span className="inline-flex items-center gap-1">
                    <MessageCircle className="h-3 w-3 text-slate-400" />
                    {c.message_count} message{c.message_count === 1 ? '' : 's'}
                  </span>
                </div>

                {c.last_message_preview && (
                  <p className="mt-1.5 flex items-start gap-1.5 truncate text-sm text-slate-600">
                    <Quote className="mt-0.5 h-3 w-3 shrink-0 text-slate-300" />
                    <span className="truncate">{c.last_message_preview}</span>
                  </p>
                )}
              </Link>

              <div className="flex shrink-0 items-center gap-2 pt-0.5">
                <button
                  title="Unarchive"
                  className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 transition-colors hover:bg-emerald-100"
                  onClick={() => handleUnarchive(c)}
                >
                  <ArchiveRestore className="h-4 w-4" />
                </button>
                <button
                  title="Delete"
                  className="flex h-7 w-7 items-center justify-center rounded-lg bg-red-50 text-red-600 transition-colors hover:bg-red-100"
                  onClick={() => setDeleteTarget(c)}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {deleteTarget && (
        <ConfirmDialog
          title="Delete conversation"
          message={`Permanently delete the conversation with ${deleteTarget.visitor_name ?? 'this visitor'}? This cannot be undone.`}
          confirmLabel="Delete"
          danger
          onConfirm={handleDelete}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  )
}

function ArchivedLeads() {
  const { notify } = useToast()
  const [leads, setLeads] = useState<Lead[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Lead | null>(null)

  async function load(isManualRefresh = false) {
    if (isManualRefresh) setRefreshing(true)
    else setLoading(true)
    setError(null)
    try {
      const { data } = await leadsApi.list({ archived: true, page: 1, page_size: 50 })
      setLeads(data.items)
      setTotal(data.total)
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
  }, [])

  async function handleUnarchive(lead: Lead) {
    try {
      await leadsApi.unarchive(lead.id)
      setLeads((prev) => prev.filter((l) => l.id !== lead.id))
      setTotal((t) => t - 1)
      notify('Lead moved back to Leads')
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
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-sm text-slate-500">
          {total} archived lead{total === 1 ? '' : 's'}
        </span>
        <Button variant="secondary" onClick={() => load(true)}>
          <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {error && <ErrorBanner message={error} />}
      {loading && <LoadingSpinner />}

      {!loading && !error && leads.length === 0 && (
        <EmptyState title="Nothing archived" description="Leads you archive will show up here." />
      )}

      {!loading && leads.length > 0 && (
        <ul className="space-y-2.5">
          {leads.map((lead) => (
            <li key={lead.id} className="flex items-start gap-4 rounded-2xl border border-slate-200 bg-white p-4">
              <div className="shrink-0">
                <div
                  className={`flex h-11 w-11 items-center justify-center rounded-full text-sm font-semibold ${avatarColor(lead.id)}`}
                >
                  {initials(lead.name)}
                </div>
              </div>

              <Link to={`/conversations/${lead.conversation_id}`} className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="truncate font-semibold text-slate-900">{lead.name ?? 'Anonymous'}</span>
                    <Badge status={lead.source} />
                  </div>
                  <span className="shrink-0 text-xs text-slate-400">{timeAgo(lead.archived_at)}</span>
                </div>

                <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
                  {lead.phone && (
                    <span className="inline-flex items-center gap-1">
                      <Phone className="h-3 w-3 text-slate-400" />
                      {lead.phone}
                    </span>
                  )}
                  {lead.email && (
                    <span className="inline-flex items-center gap-1">
                      <Mail className="h-3 w-3 text-slate-400" />
                      {lead.email}
                    </span>
                  )}
                  <span>Status: {lead.status}</span>
                </div>
              </Link>

              <div className="flex shrink-0 items-center gap-2 pt-0.5">
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
              </div>
            </li>
          ))}
        </ul>
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
    </div>
  )
}

export function ArchivePage() {
  const [tab, setTab] = useState<'conversations' | 'leads'>('conversations')

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-slate-900">Archive</h1>
        <p className="mt-0.5 text-sm text-slate-500">Archived conversations and leads</p>
      </div>

      <div className="flex gap-1 rounded-lg border border-slate-200 bg-slate-50 p-1 w-fit">
        <button
          onClick={() => setTab('conversations')}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
            tab === 'conversations' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
          }`}
        >
          Conversations
        </button>
        <button
          onClick={() => setTab('leads')}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
            tab === 'leads' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
          }`}
        >
          Leads
        </button>
      </div>

      {tab === 'conversations' ? <ArchivedConversations /> : <ArchivedLeads />}
    </div>
  )
}
