import { useEffect, useState, type ReactNode } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import {
  MessagesSquare,
  Activity,
  CheckCircle2,
  Clock,
  UserPlus,
  CalendarDays,
  CalendarRange,
  CalendarCheck,
  type LucideIcon,
} from 'lucide-react'
import { dashboardApi } from '../api/resources'
import type { DashboardCharts, DashboardStats } from '../api/types'
import { LoadingSpinner, ErrorBanner } from '../components/ui/Feedback'
import { apiErrorMessage } from '../api/client'

// Validated categorical order (see dataviz color-formula) — fixed slot order,
// never cycled/reassigned per value so identity stays stable across renders.
const PIE_COLORS = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4']
const GRIDLINE = '#e1e0d9'
const AXIS_TICK = { fontSize: 11, fill: '#898781' }

function StatCard({ label, value, icon: Icon, tint }: { label: string; value: string | number; icon: LucideIcon; tint: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 transition-shadow hover:shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm text-slate-500">{label}</p>
        <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${tint}`}>
          <Icon className="h-4 w-4" strokeWidth={2} />
        </span>
      </div>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">{value}</p>
    </div>
  )
}

function ChartCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <h2 className="mb-3 text-sm font-semibold text-slate-700">{title}</h2>
      {children}
    </div>
  )
}

export function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [charts, setCharts] = useState<DashboardCharts | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([dashboardApi.stats(), dashboardApi.charts()])
      .then(([statsRes, chartsRes]) => {
        setStats(statsRes.data)
        setCharts(chartsRes.data)
      })
      .catch((err) => setError(apiErrorMessage(err)))
  }, [])

  if (error) return <ErrorBanner message={error} />
  if (!stats || !charts) return <LoadingSpinner />

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-slate-900">Dashboard</h1>
        <p className="text-sm text-slate-500">Overview across every agent</p>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Total Conversations" value={stats.total_conversations} icon={MessagesSquare} tint="bg-brand-100 text-brand-700" />
        <StatCard label="Active Conversations" value={stats.active_conversations} icon={Activity} tint="bg-accent-100 text-accent-700" />
        <StatCard label="Resolved Conversations" value={stats.resolved_conversations} icon={CheckCircle2} tint="bg-emerald-100 text-emerald-700" />
        <StatCard
          label="Avg. Response Time"
          value={stats.average_response_time_seconds ? `${Math.round(stats.average_response_time_seconds)}s` : '—'}
          icon={Clock}
          tint="bg-amber-100 text-amber-700"
        />
        <StatCard label="New Leads" value={stats.new_leads} icon={UserPlus} tint="bg-brand-100 text-brand-700" />
        <StatCard label="Leads Today" value={stats.leads_today} icon={CalendarDays} tint="bg-accent-100 text-accent-700" />
        <StatCard label="Leads This Week" value={stats.leads_this_week} icon={CalendarRange} tint="bg-accent-100 text-accent-700" />
        <StatCard label="Leads This Month" value={stats.leads_this_month} icon={CalendarCheck} tint="bg-accent-100 text-accent-700" />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <ChartCard title="Conversations Over Time">
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={charts.conversations_over_time}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRIDLINE} />
              <XAxis dataKey="day" tick={AXIS_TICK} />
              <YAxis allowDecimals={false} tick={AXIS_TICK} />
              <Tooltip />
              <Line type="monotone" dataKey="count" stroke={PIE_COLORS[0]} strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Leads Over Time">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={charts.leads_over_time}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRIDLINE} />
              <XAxis dataKey="day" tick={AXIS_TICK} />
              <YAxis allowDecimals={false} tick={AXIS_TICK} />
              <Tooltip />
              <Bar dataKey="count" fill={PIE_COLORS[1]} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="AI vs. Human Conversations">
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={charts.ai_vs_human_conversations} dataKey="count" nameKey="status" outerRadius={80} label>
                {charts.ai_vs_human_conversations.map((_, i) => (
                  <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Conversation Status Breakdown">
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={charts.conversation_status_breakdown} dataKey="count" nameKey="status" outerRadius={80} label>
                {charts.conversation_status_breakdown.map((_, i) => (
                  <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </div>
  )
}
