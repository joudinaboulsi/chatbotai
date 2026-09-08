import { useEffect, useState } from 'react'
import { Plus } from 'lucide-react'
import { agentsApi, operatorsApi } from '../api/resources'
import { apiErrorMessage } from '../api/client'
import type { Agent, Operator, UserRole } from '../api/types'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Input, Select } from '../components/ui/Field'
import { Modal } from '../components/ui/Modal'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'
import { ErrorBanner, LoadingSpinner, EmptyState } from '../components/ui/Feedback'
import { useToast } from '../components/ui/Toast'
import { useAuth } from '../context/AuthContext'

export function OperatorsPage() {
  const { notify } = useToast()
  const { user } = useAuth()
  const [operators, setOperators] = useState<Operator[]>([])
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [editing, setEditing] = useState<Operator | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Operator | null>(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const [opsRes, agentsRes] = await Promise.all([operatorsApi.list(), agentsApi.list({ page: 1, page_size: 100 })])
      setOperators(opsRes.data)
      setAgents(agentsRes.data.items)
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function handleDelete() {
    if (!deleteTarget) return
    try {
      await operatorsApi.remove(deleteTarget.id)
      notify('Operator deleted')
      setDeleteTarget(null)
      load()
    } catch (err) {
      notify(apiErrorMessage(err), 'error')
    }
  }

  function agentNames(ids: string[]) {
    if (ids.length === 0) return '—'
    return ids.map((id) => agents.find((a) => a.id === id)?.name ?? id).join(', ')
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">Agent Operators</h1>
        <Button onClick={() => setShowCreate(true)}><Plus className="h-4 w-4" />Add Operator</Button>
      </div>

      {error && <ErrorBanner message={error} />}
      {loading && <LoadingSpinner />}
      {!loading && operators.length === 0 && <EmptyState title="No operators yet" />}

      {!loading && operators.length > 0 && (
        <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Email</th>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Assigned Agents</th>
                <th className="px-4 py-3">Last Login</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {operators.map((op) => (
                <tr key={op.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-slate-900">{op.name}</td>
                  <td className="px-4 py-3 text-slate-600">{op.email}</td>
                  <td className="px-4 py-3">
                    <Badge status={op.role} />
                  </td>
                  <td className="px-4 py-3">
                    <Badge status={op.status} />
                  </td>
                  <td className="px-4 py-3 text-slate-600">{agentNames(op.assigned_agent_ids)}</td>
                  <td className="px-4 py-3 text-slate-500">
                    {op.last_login_at ? new Date(op.last_login_at).toLocaleString() : 'Never'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button className="mr-3 text-brand-600 hover:underline" onClick={() => setEditing(op)}>
                      Edit
                    </button>
                    {op.id !== user?.id && (
                      <button className="text-red-600 hover:underline" onClick={() => setDeleteTarget(op)}>
                        Delete
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showCreate && (
        <OperatorFormModal agents={agents} onClose={() => setShowCreate(false)} onSaved={() => { setShowCreate(false); load() }} />
      )}
      {editing && (
        <OperatorFormModal
          agents={agents}
          operator={editing}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); load() }}
        />
      )}
      {deleteTarget && (
        <ConfirmDialog
          title="Delete operator"
          message={`Remove ${deleteTarget.name}'s access? This cannot be undone.`}
          confirmLabel="Delete"
          danger
          onConfirm={handleDelete}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  )
}

function OperatorFormModal({
  agents,
  operator,
  onClose,
  onSaved,
}: {
  agents: Agent[]
  operator?: Operator
  onClose: () => void
  onSaved: () => void
}) {
  const { notify } = useToast()
  const [name, setName] = useState(operator?.name ?? '')
  const [email, setEmail] = useState(operator?.email ?? '')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<UserRole>(operator?.role ?? 'support_agent')
  const [assignedAgentIds, setAssignedAgentIds] = useState<string[]>(operator?.assigned_agent_ids ?? [])
  const [saving, setSaving] = useState(false)

  async function handleSubmit() {
    setSaving(true)
    try {
      if (operator) {
        await operatorsApi.update(operator.id, { name, role, assigned_agent_ids: assignedAgentIds })
      } else {
        await operatorsApi.create({ name, email, password, role, assigned_agent_ids: assignedAgentIds })
      }
      notify(operator ? 'Operator updated' : 'Operator created')
      onSaved()
    } catch (err) {
      notify(apiErrorMessage(err), 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title={operator ? 'Edit Operator' : 'Add Operator'} onClose={onClose}>
      <div className="space-y-4">
        <Input label="Name" required value={name} onChange={(e) => setName(e.target.value)} />
        <Input label="Email" type="email" required disabled={!!operator} value={email} onChange={(e) => setEmail(e.target.value)} />
        {!operator && (
          <Input label="Password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        )}
        <Select label="Role" value={role} onChange={(e) => setRole(e.target.value as UserRole)}>
          <option value="support_agent">Support Agent</option>
          <option value="admin">Admin</option>
          <option value="super_admin">Super Admin</option>
        </Select>
        <div>
          <span className="mb-1 block text-sm font-medium text-slate-700">Assigned Agents</span>
          <div className="max-h-40 space-y-1 overflow-y-auto rounded-lg border border-slate-200 p-2">
            {agents.map((agent) => (
              <label key={agent.id} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={assignedAgentIds.includes(agent.id)}
                  onChange={(e) =>
                    setAssignedAgentIds((prev) =>
                      e.target.checked ? [...prev, agent.id] : prev.filter((id) => id !== agent.id),
                    )
                  }
                />
                {agent.name}
              </label>
            ))}
          </div>
        </div>
        <Button
          className="w-full"
          disabled={saving || !name.trim() || (!operator && (!email.trim() || password.length < 8))}
          onClick={handleSubmit}
        >
          {operator ? 'Save Changes' : 'Create Operator'}
        </Button>
      </div>
    </Modal>
  )
}
