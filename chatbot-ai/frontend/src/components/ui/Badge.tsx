const COLOR_MAP: Record<string, string> = {
  active: 'bg-emerald-100 text-emerald-700',
  inactive: 'bg-slate-100 text-slate-600',
  pending: 'bg-amber-100 text-amber-700',
  processing: 'bg-accent-100 text-accent-700',
  completed: 'bg-emerald-100 text-emerald-700',
  failed: 'bg-red-100 text-red-700',
  ai_active: 'bg-accent-100 text-accent-700',
  waiting_for_agent: 'bg-amber-100 text-amber-700',
  human_active: 'bg-brand-100 text-brand-700',
  resolved: 'bg-emerald-100 text-emerald-700',
  closed: 'bg-slate-100 text-slate-600',
  new: 'bg-accent-100 text-accent-700',
  contacted: 'bg-amber-100 text-amber-700',
  qualified: 'bg-brand-100 text-brand-700',
  converted: 'bg-emerald-100 text-emerald-700',
  waiting: 'bg-amber-100 text-amber-700',
  assigned: 'bg-accent-100 text-accent-700',
  active_request: 'bg-brand-100 text-brand-700',
  super_admin: 'bg-brand-100 text-brand-700',
  admin: 'bg-accent-100 text-accent-700',
  support_agent: 'bg-slate-100 text-slate-600',
}

export function Badge({ status }: { status: string }) {
  const classes = COLOR_MAP[status] ?? 'bg-slate-100 text-slate-600'
  const label = status.replace(/_/g, ' ')
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${classes}`}>
      {label}
    </span>
  )
}
