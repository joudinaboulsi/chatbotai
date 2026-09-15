import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, ChevronLeft, ChevronRight } from 'lucide-react'
import { conversationsApi } from '../api/resources'
import { apiErrorMessage } from '../api/client'
import type { ConversationDetail } from '../api/types'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { ErrorBanner, LoadingSpinner } from '../components/ui/Feedback'
import { useToast } from '../components/ui/Toast'

const SENDER_STYLES: Record<string, string> = {
  visitor: 'bg-brand-600 text-white self-end',
  ai: 'bg-slate-100 text-slate-900 self-start',
  operator: 'bg-green-100 text-green-900 self-start',
  system: 'bg-amber-50 text-amber-800 self-start italic',
}

export function ConversationDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const { notify } = useToast()
  const [conversation, setConversation] = useState<ConversationDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reply, setReply] = useState('')
  const [sending, setSending] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  const navIds = (location.state as { ids?: string[] } | null)?.ids
  const navIndex = navIds && id ? navIds.indexOf(id) : -1
  const prevId = navIndex > 0 ? navIds![navIndex - 1] : null
  const nextId = navIds && navIndex >= 0 && navIndex < navIds.length - 1 ? navIds![navIndex + 1] : null

  function goTo(targetId: string) {
    navigate(`/conversations/${targetId}`, { state: { ids: navIds } })
  }

  async function load() {
    if (!id) return
    try {
      const { data } = await conversationsApi.get(id)
      setConversation(data)
    } catch (err) {
      setError(apiErrorMessage(err))
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [conversation?.messages.length])

  async function handleSend() {
    if (!id || !reply.trim()) return
    setSending(true)
    try {
      await conversationsApi.sendMessage(id, reply.trim())
      setReply('')
      await load()
    } catch (err) {
      notify(apiErrorMessage(err), 'error')
    } finally {
      setSending(false)
    }
  }

  async function handleAssign() {
    if (!id) return
    try {
      await conversationsApi.assign(id)
      notify('Conversation assigned to you')
      load()
    } catch (err) {
      notify(apiErrorMessage(err), 'error')
    }
  }

  async function handleResolve() {
    if (!id) return
    await conversationsApi.resolve(id)
    notify('Conversation resolved')
    load()
  }

  async function handleClose() {
    if (!id) return
    await conversationsApi.close(id)
    notify('Conversation closed')
    load()
  }

  async function handleArchive() {
    if (!id) return
    await conversationsApi.archive(id)
    notify('Conversation archived')
    navigate('/conversations')
  }

  if (error) return <ErrorBanner message={error} />
  if (!conversation) return <LoadingSpinner />

  const canReply = conversation.status === 'human_active' || conversation.status === 'waiting_for_agent'

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <button
          onClick={() => navigate('/conversations')}
          className="flex items-center gap-1 rounded-md bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-200"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back
        </button>

        {navIds && (
          <div className="flex items-center gap-1.5">
            <button
              disabled={!prevId}
              onClick={() => prevId && goTo(prevId)}
              className="flex items-center gap-1 rounded-md bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              Prev
            </button>
            <button
              disabled={!nextId}
              onClick={() => nextId && goTo(nextId)}
              className="flex items-center gap-1 rounded-md bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Next
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
        <div className="space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <h2 className="mb-2 font-semibold text-slate-900">Visitor</h2>
            <p className="text-sm text-slate-600">Name: {conversation.visitor_name ?? '—'}</p>
            <p className="text-sm text-slate-600">Email: {conversation.visitor_email ?? '—'}</p>
            <p className="text-sm text-slate-600">Phone: {conversation.visitor_phone ?? '—'}</p>
            <div className="mt-3">
              <Badge status={conversation.status} />
            </div>
          </div>
          <div className="space-y-2 rounded-2xl border border-slate-200 bg-white p-4">
            {conversation.status === 'waiting_for_agent' && (
              <Button className="w-full" onClick={handleAssign}>
                Accept Conversation
              </Button>
            )}
            {(conversation.status === 'human_active' || conversation.status === 'ai_active') && (
              <Button variant="secondary" className="w-full" onClick={handleResolve}>
                Mark Resolved
              </Button>
            )}
            <Button variant="secondary" className="w-full" onClick={handleClose}>
              Close Conversation
            </Button>
            <Button variant="secondary" className="w-full" onClick={handleArchive}>
              Archive
            </Button>
          </div>
        </div>

        <div className="flex h-[70vh] flex-col rounded-2xl border border-slate-200 bg-white">
          <div className="flex-1 space-y-3 overflow-y-auto p-4">
            {conversation.messages.map((m) => (
              <div
                key={m.id}
                className={`flex max-w-[75%] flex-col rounded-lg px-3 py-2 text-sm ${SENDER_STYLES[m.sender_type] ?? ''}`}
              >
                <span className="mb-0.5 text-[10px] uppercase opacity-60">{m.sender_type}</span>
                {m.content}
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
          <div className="border-t border-slate-200 p-3">
            {canReply ? (
              <div className="flex gap-2">
                <input
                  value={reply}
                  onChange={(e) => setReply(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                  placeholder="Type a reply…"
                  className="flex-1 rounded-full border border-slate-300 px-4 py-2 text-sm focus:border-brand-500 focus:outline-none"
                />
                <Button disabled={sending || !reply.trim()} onClick={handleSend}>
                  Send
                </Button>
              </div>
            ) : (
              <p className="text-center text-xs text-slate-400">
                This conversation is not active for a human agent. Accept it to reply.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
