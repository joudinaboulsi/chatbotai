import { useEffect, useRef, useState, type MouseEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell, X } from 'lucide-react'
import { notificationsApi } from '../../api/resources'
import { getAccessToken } from '../../api/client'
import type { NotificationOut } from '../../api/types'

// WebSocket push is primary; this is just a resilience fallback in case a
// connection silently drops without firing onclose (e.g. some proxies).
const FALLBACK_POLL_INTERVAL_MS = 60000
const RECONNECT_DELAY_MS = 3000

export function NotificationBell() {
  const [notifications, setNotifications] = useState<NotificationOut[]>([])
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const navigate = useNavigate()

  async function load() {
    try {
      const { data } = await notificationsApi.list()
      setNotifications(data)
    } catch {
      // silent — notification bell shouldn't disrupt the rest of the app
    }
  }

  useEffect(() => {
    load()
    const pollTimer = setInterval(load, FALLBACK_POLL_INTERVAL_MS)

    let cancelled = false
    let reconnectTimer: ReturnType<typeof setTimeout>

    function connect() {
      const token = getAccessToken()
      if (!token || cancelled) return

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(`${protocol}//${window.location.host}/api/ws/notifications?token=${token}`)
      wsRef.current = ws

      ws.onmessage = (event) => {
        try {
          const notification: NotificationOut = JSON.parse(event.data)
          setNotifications((prev) => [notification, ...prev])
        } catch {
          // ignore malformed payloads
        }
      }
      ws.onclose = () => {
        if (!cancelled) reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS)
      }
      ws.onerror = () => ws.close()
    }
    connect()

    return () => {
      cancelled = true
      clearInterval(pollTimer)
      clearTimeout(reconnectTimer)
      wsRef.current?.close()
    }
  }, [])

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  const unreadCount = notifications.filter((n) => !n.is_read).length

  async function handleClick(n: NotificationOut) {
    if (!n.is_read) {
      await notificationsApi.markRead(n.id)
      setNotifications((prev) => prev.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)))
    }
    setOpen(false)
    if (n.link) navigate(n.link)
  }

  async function handleClear(e: MouseEvent, id: string) {
    e.stopPropagation()
    setNotifications((prev) => prev.filter((n) => n.id !== id))
    try {
      await notificationsApi.clear(id)
    } catch {
      load()
    }
  }

  async function handleClearAll() {
    setNotifications([])
    try {
      await notificationsApi.clearAll()
    } catch {
      load()
    }
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="relative rounded-full p-2 text-slate-500 hover:bg-slate-100"
        aria-label="Notifications"
      >
        <Bell className="h-5 w-5" />
        {unreadCount > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-semibold text-white">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-2 w-80 rounded-xl border border-slate-200 bg-white shadow-lg shadow-ink-950/10">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <span className="text-sm font-semibold text-slate-900">Notifications</span>
            <div className="flex items-center gap-3">
              {unreadCount > 0 && (
                <button
                  className="text-xs font-medium text-brand-600 hover:underline"
                  onClick={async () => {
                    await notificationsApi.markAllRead()
                    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })))
                  }}
                >
                  Mark all read
                </button>
              )}
              {notifications.length > 0 && (
                <button className="text-xs font-medium text-slate-500 hover:underline" onClick={handleClearAll}>
                  Clear all
                </button>
              )}
            </div>
          </div>
          <div className="max-h-96 overflow-y-auto">
            {notifications.length === 0 && (
              <p className="px-4 py-6 text-center text-sm text-slate-500">No notifications yet</p>
            )}
            {notifications.map((n) => (
              <div
                key={n.id}
                role="button"
                tabIndex={0}
                onClick={() => handleClick(n)}
                onKeyDown={(e) => e.key === 'Enter' && handleClick(n)}
                className={`group flex w-full items-start gap-2 border-b border-slate-50 px-4 py-3 text-left text-sm hover:bg-slate-50 ${
                  n.is_read ? 'opacity-60' : ''
                }`}
              >
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-slate-900">{n.title}</p>
                  {n.body && <p className="mt-0.5 text-xs text-slate-500">{n.body}</p>}
                  <p className="mt-1 text-[11px] text-slate-400">{new Date(n.created_at).toLocaleString()}</p>
                </div>
                <button
                  onClick={(e) => handleClear(e, n.id)}
                  className="shrink-0 rounded p-1 text-slate-300 opacity-0 transition-opacity hover:bg-slate-200 hover:text-slate-600 group-hover:opacity-100"
                  aria-label="Clear notification"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
