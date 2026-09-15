import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, Send } from 'lucide-react'
import { conversationsApi, leadsApi } from '../../api/resources'
import { apiErrorMessage } from '../../api/client'
import type { ConversationDetail, Lead } from '../../api/types'
import { useToast } from '../ui/Toast'

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export function WhatsAppPreviewModal({ lead, onClose }: { lead: Lead; onClose: () => void }) {
  const { notify } = useToast()
  const [conversation, setConversation] = useState<ConversationDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [text, setText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let cancelled = false
    leadsApi
      .startWhatsapp(lead.id)
      .then(({ data }) => {
        if (!cancelled) setConversation(data)
      })
      .catch((err) => {
        if (!cancelled) setError(apiErrorMessage(err))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lead.id])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [conversation?.messages.length])

  async function handleSend() {
    if (!conversation || !text.trim() || sending) return
    const outgoing = text.trim()
    setText('')
    setSending(true)
    try {
      const { data } = await conversationsApi.whatsappReply(conversation.id, outgoing)
      setConversation(data)
    } catch (err) {
      notify(apiErrorMessage(err), 'error')
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/50 p-4 backdrop-blur-[2px]" onClick={onClose}>
      <div
        className="flex h-[85vh] w-full max-w-md flex-col overflow-hidden rounded-2xl bg-[#e5ddd5] shadow-2xl shadow-ink-950/20"
        onClick={(e) => e.stopPropagation()}
      >
        {/* WhatsApp-style header */}
        <div className="flex items-center gap-3 bg-[#075e54] px-4 py-3 text-white">
          <button onClick={onClose} className="rounded-full p-1 hover:bg-white/10" aria-label="Close">
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#128c7e] text-sm font-semibold">
            {(lead.name ?? '?').slice(0, 1).toUpperCase()}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold">{lead.name ?? 'Unknown visitor'}</p>
            <p className="text-xs text-white/70">{lead.phone ?? 'no phone on file'} · AI preview, not sent</p>
          </div>
        </div>

        {/* Chat body */}
        <div
          className="flex-1 space-y-2 overflow-y-auto px-3 py-4"
          style={{
            backgroundImage:
              "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='60' height='60' viewBox='0 0 60 60'%3E%3Cg fill='%23d8cfc4' fill-opacity='0.4'%3E%3Cpath d='M0 0h30v30H0zM30 30h30v30H30z'/%3E%3C/g%3E%3C/svg%3E\")",
          }}
        >
          {loading && (
            <div className="flex justify-center pt-10">
              <div className="rounded-full bg-white/80 px-4 py-2 text-xs text-slate-500 shadow-sm">Starting conversation…</div>
            </div>
          )}

          {error && (
            <div className="flex justify-center pt-10">
              <div className="max-w-xs rounded-lg bg-red-50 px-4 py-3 text-center text-xs text-red-700 shadow-sm">{error}</div>
            </div>
          )}

          {conversation?.messages.map((m) => {
            const isVisitor = m.sender_type === 'visitor'
            return (
              <div key={m.id} className={`flex ${isVisitor ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[75%] rounded-lg px-3 py-2 text-sm shadow-sm ${
                    isVisitor ? 'bg-[#d9fdd3] text-slate-900' : 'bg-white text-slate-900'
                  }`}
                >
                  <p className="whitespace-pre-wrap">{m.content}</p>
                  <p className="mt-1 text-right text-[10px] text-slate-400">{formatTime(m.created_at)}</p>
                </div>
              </div>
            )
          })}

          {sending && (
            <div className="flex justify-start">
              <div className="rounded-lg bg-white px-3 py-2 text-sm text-slate-400 shadow-sm">…</div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input bar */}
        <div className="flex items-center gap-2 bg-[#f0f0f0] px-3 py-2.5">
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Type a message as the visitor…"
            disabled={loading || !conversation}
            className="flex-1 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm focus:border-[#25d366] focus:outline-none focus:ring-1 focus:ring-[#25d366] disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={loading || !conversation || sending || !text.trim()}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#25d366] text-white transition-opacity disabled:opacity-40"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
