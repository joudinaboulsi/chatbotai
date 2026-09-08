import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Bot,
  BookOpen,
  MessagesSquare,
  Target,
  Headphones,
  Users,
  Settings,
} from 'lucide-react'

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/agents', label: 'AI Agents', icon: Bot },
  { to: '/knowledge-base', label: 'Knowledge Base', icon: BookOpen },
  { to: '/conversations', label: 'Conversations', icon: MessagesSquare },
  { to: '/leads', label: 'Leads', icon: Target },
  { to: '/live-agents', label: 'Live Agents', icon: Headphones },
  { to: '/operators', label: 'Agent Operators', icon: Users },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex h-full w-64 flex-col bg-ink-950 text-slate-300">
      <div className="flex h-16 items-center gap-2.5 px-5">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-500 shadow-[0_0_0_1px_rgba(255,255,255,0.08)]">
          <svg viewBox="0 0 24 24" className="h-4.5 w-4.5 text-white" fill="none">
            <path
              d="M12 3c-4.97 0-9 3.582-9 8 0 2.29 1.09 4.352 2.845 5.81-.096 1.02-.47 2.058-1.213 3.06-.14.19.008.453.24.42 1.79-.256 3.19-.856 4.24-1.55A10.6 10.6 0 0 0 12 19c4.97 0 9-3.582 9-8s-4.03-8-9-8Z"
              fill="currentColor"
            />
            <circle cx="8.5" cy="11" r="1.15" fill="#150f2e" />
            <circle cx="12" cy="11" r="1.15" fill="#150f2e" />
            <circle cx="15.5" cy="11" r="1.15" fill="#150f2e" />
          </svg>
        </span>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold leading-tight text-white">AI Chatbot Platform</p>
          <p className="text-[11px] leading-tight text-slate-500">Admin Console</p>
        </div>
      </div>

      <div className="flex-1 space-y-0.5 overflow-y-auto px-3 py-3">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon
          return (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={onNavigate}
              className={({ isActive }) =>
                `group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-white/10 text-white'
                    : 'text-slate-400 hover:bg-white/5 hover:text-slate-100'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon
                    className={`h-[18px] w-[18px] shrink-0 ${isActive ? 'text-accent-400' : 'text-slate-500 group-hover:text-slate-300'}`}
                    strokeWidth={2}
                  />
                  {item.label}
                </>
              )}
            </NavLink>
          )
        })}
      </div>
    </nav>
  )
}
