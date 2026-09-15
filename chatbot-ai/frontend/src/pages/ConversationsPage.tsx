import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronLeft, ChevronRight, MessageCircle, Phone, Quote, RefreshCw, Search } from 'lucide-react'
import { conversationsApi } from '../api/resources'
import { apiErrorMessage } from '../api/client'
import type { ConversationListItem, ConversationStatus } from '../api/types'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { ErrorBanner, LoadingSpinner, EmptyState } from '../components/ui/Feedback'

const PAGE_SIZE = 10

const STATUS_TABS: { value: ConversationStatus | ''; label: string }[] = [
  { value: '', label: 'All' },
  { value: 'ai_active', label: 'AI Active' },
  { value: 'waiting_for_agent', label: 'Waiting' },
  { value: 'human_active', label: 'Human Active' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'closed', label: 'Closed' },
]

// Same status→tone mapping Badge.tsx already uses, just as a solid dot
// instead of a soft background — keeps the dot (on the avatar) and the
// badge next to the name reading as the same status, not two systems.
const STATUS_DOT: Record<ConversationStatus, string> = {
  ai_active: 'bg-accent-500',
  waiting_for_agent: 'bg-amber-500',
  human_active: 'bg-brand-500',
  resolved: 'bg-emerald-500',
  closed: 'bg-slate-400',
}

const EMPTY_STATUS_COUNTS: Record<ConversationStatus, number> = {
  ai_active: 0,
  waiting_for_agent: 0,
  human_active: 0,
  resolved: 0,
  closed: 0,
}

const SELECT_CLASS =
  'rounded-xl border border-slate-200 bg-slate-50 py-2.5 pl-3.5 pr-9 text-sm text-slate-700 transition-colors hover:border-slate-300 focus:border-brand-500 focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-500'

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

export function ConversationsPage() {
  const [conversations, setConversations] = useState<ConversationListItem[]>([])
  const [total, setTotal] = useState(0)
  const [statusCounts, setStatusCounts] = useState<Record<ConversationStatus, number>>(EMPTY_STATUS_COUNTS)
  const [statusFilter, setStatusFilter] = useState<ConversationStatus | ''>('')
  const [hasLead, setHasLead] = useState<'' | 'true' | 'false'>('')
  const [sort, setSort] = useState<'newest' | 'oldest' | 'most_messages'>('newest')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const grandTotal = useMemo(
    () => Object.values(statusCounts).reduce((sum, n) => sum + n, 0),
    [statusCounts],
  )

  async function load(isManualRefresh = false) {
    if (isManualRefresh) setRefreshing(true)
    else setLoading(true)
    setError(null)
    try {
      const { data } = await conversationsApi.list({
        status: statusFilter || undefined,
        has_lead: hasLead === '' ? undefined : hasLead === 'true',
        sort,
        page,
        page_size: PAGE_SIZE,
      })
      setConversations(data.items)
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
  }, [statusFilter, hasLead, sort, page])

  const filtered = useMemo(() => {
    if (!search.trim()) return conversations
    const q = search.trim().toLowerCase()
    return conversations.filter((c) =>
      [c.visitor_name, c.visitor_email, c.visitor_phone].some((v) => v?.toLowerCase().includes(q)),
    )
  }, [conversations, search])

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-slate-900">Conversations</h1>
          <p className="mt-0.5 text-sm text-slate-500">{grandTotal} conversation{grandTotal === 1 ? '' : 's'}</p>
        </div>
        <Button variant="secondary" onClick={() => load(true)}>
          <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="relative flex-1 min-w-[220px]">
            <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              placeholder="Search by name, email, or phone…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2.5 pl-10 pr-3 text-sm transition-colors hover:border-slate-300 focus:border-brand-500 focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
          </div>

          <select
            value={hasLead}
            onChange={(e) => {
              setHasLead(e.target.value as '' | 'true' | 'false')
              setPage(1)
            }}
            className={SELECT_CLASS}
          >
            <option value="">All conversations</option>
            <option value="true">Has lead</option>
            <option value="false">No lead</option>
          </select>

          <select
            value={sort}
            onChange={(e) => {
              setSort(e.target.value as 'newest' | 'oldest' | 'most_messages')
              setPage(1)
            }}
            className={SELECT_CLASS}
          >
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="most_messages">Most messages</option>
          </select>
        </div>

        <div className="flex flex-wrap gap-1.5 rounded-xl bg-slate-100 p-1">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.value}
              onClick={() => {
                setStatusFilter(tab.value)
                setPage(1)
              }}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
                statusFilter === tab.value
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              {tab.label} <span className="text-slate-400">{tab.value === '' ? grandTotal : statusCounts[tab.value]}</span>
            </button>
          ))}
        </div>
      </div>

      {error && <ErrorBanner message={error} />}
      {loading && <LoadingSpinner />}

      {!loading && !error && filtered.length === 0 && (
        <EmptyState
          title="No conversations found"
          description={search ? 'Try a different search term.' : 'Conversations will show up here once visitors start chatting.'}
        />
      )}

      {!loading && filtered.length > 0 && (
        <>
          <ul className="space-y-2.5">
            {filtered.map((c) => (
              <li key={c.id}>
                <Link
                  to={`/conversations/${c.id}`}
                  state={{ ids: filtered.map((x) => x.id) }}
                  className="group flex items-start gap-4 rounded-2xl border border-slate-200 bg-white p-4 transition-all hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md hover:shadow-slate-900/5"
                >
                  <div className="relative shrink-0">
                    <div
                      className={`flex h-11 w-11 items-center justify-center rounded-full text-sm font-semibold ${avatarColor(c.id)}`}
                    >
                      {initials(c.visitor_name)}
                    </div>
                    <span
                      className={`absolute -bottom-0.5 -right-0.5 h-3.5 w-3.5 rounded-full ring-2 ring-white ${STATUS_DOT[c.status]}`}
                    />
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex min-w-0 items-center gap-2">
                        <span className="truncate font-semibold text-slate-900">{c.visitor_name ?? 'Anonymous'}</span>
                        <Badge status={c.status} />
                      </div>
                      <span className="shrink-0 text-xs text-slate-400">{timeAgo(c.last_message_at)}</span>
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
                  </div>
                </Link>
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
        </>
      )}
    </div>
  )
}
