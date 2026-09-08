import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { MoreHorizontal } from 'lucide-react'

export function RowActionsMenu({
  open,
  onToggle,
  onClose,
  actions,
}: {
  open: boolean
  onToggle: () => void
  onClose: () => void
  actions: { label: string; onClick: () => void; danger?: boolean }[]
}) {
  const buttonRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const [position, setPosition] = useState<{ top: number; right: number } | null>(null)

  useLayoutEffect(() => {
    if (!open || !buttonRef.current) return
    const rect = buttonRef.current.getBoundingClientRect()
    setPosition({ top: rect.bottom + 4, right: window.innerWidth - rect.right })
  }, [open])

  useEffect(() => {
    if (!open) return
    function handlePointerDown(e: MouseEvent) {
      const target = e.target as Node
      if (buttonRef.current?.contains(target) || menuRef.current?.contains(target)) return
      onClose()
    }
    // Menu is portaled and fixed-positioned from the button's rect at open time —
    // any scroll/resize invalidates that rect, so just close rather than drift.
    function handleScrollOrResize() {
      onClose()
    }
    document.addEventListener('mousedown', handlePointerDown)
    window.addEventListener('scroll', handleScrollOrResize, true)
    window.addEventListener('resize', handleScrollOrResize)
    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      window.removeEventListener('scroll', handleScrollOrResize, true)
      window.removeEventListener('resize', handleScrollOrResize)
    }
  }, [open, onClose])

  return (
    <>
      <button
        ref={buttonRef}
        onClick={onToggle}
        className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
        aria-label="Actions"
      >
        <MoreHorizontal className="h-4 w-4" />
      </button>
      {open &&
        position &&
        createPortal(
          <div
            ref={menuRef}
            style={{ position: 'fixed', top: position.top, right: position.right }}
            className="z-50 w-40 rounded-xl border border-slate-200 bg-white py-1 shadow-lg shadow-ink-950/10"
          >
            {actions.map((action) => (
              <button
                key={action.label}
                onClick={() => {
                  action.onClick()
                  onClose()
                }}
                className={`block w-full px-3 py-1.5 text-left text-sm hover:bg-slate-50 ${
                  action.danger ? 'text-red-600' : 'text-slate-700'
                }`}
              >
                {action.label}
              </button>
            ))}
          </div>,
          document.body,
        )}
    </>
  )
}
