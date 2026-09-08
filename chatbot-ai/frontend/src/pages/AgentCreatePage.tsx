import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { agentsApi } from '../api/resources'
import { apiErrorMessage } from '../api/client'
import { Button } from '../components/ui/Button'
import { ErrorBanner } from '../components/ui/Feedback'
import { EmbedCodeModal } from '../components/ui/EmbedCodeModal'
import { AgentBasicForm, type AgentBasicFormValue } from '../components/agents/AgentBasicForm'

const EMPTY_FORM: AgentBasicFormValue = {
  name: '',
  description: '',
  displayName: '',
  industry: '',
  languageRestriction: 'none',
  restrictedLanguages: [],
  remarks: '',
  notificationEmail: '',
}

export function AgentCreatePage() {
  const navigate = useNavigate()
  const [form, setForm] = useState(EMPTY_FORM)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [createdAgentId, setCreatedAgentId] = useState<string | null>(null)
  const [embedCode, setEmbedCode] = useState<string | null>(null)

  function canSubmit() {
    return form.name.trim().length > 0 && form.displayName.trim().length > 0 && form.industry.trim().length > 0
  }

  async function handleCreate() {
    setSaving(true)
    setError(null)
    try {
      const { data: agent } = await agentsApi.create({
        name: form.name,
        company_name: form.displayName,
        industry: form.industry,
        description: form.description || undefined,
        remarks: form.remarks || undefined,
        languages: form.languageRestriction === 'specific' ? form.restrictedLanguages : [],
        notification_email: form.notificationEmail || undefined,
      })
      await agentsApi.updateBranding(agent.id, { display_agent_name: form.displayName })
      const { data } = await agentsApi.embedCode(agent.id)
      setCreatedAgentId(agent.id)
      setEmbedCode(data.embed_code)
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  if (embedCode && createdAgentId) {
    return <EmbedCodeModal embedCode={embedCode} onClose={() => navigate(`/agents/${createdAgentId}`)} />
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Create New Agent</h1>
        <p className="text-sm text-slate-500">Set up a new AI agent's basic details.</p>
      </div>

      {error && <ErrorBanner message={error} />}

      <div className="max-w-2xl space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
        <AgentBasicForm value={form} onChange={setForm} />

        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => navigate('/agents')}>
            Cancel
          </Button>
          <Button disabled={!canSubmit() || saving} onClick={handleCreate}>
            {saving ? 'Creating…' : 'Create Agent'}
          </Button>
        </div>
      </div>
    </div>
  )
}
