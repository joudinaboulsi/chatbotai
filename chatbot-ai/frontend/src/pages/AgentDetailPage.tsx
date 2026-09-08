import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { agentsApi, type AgentCreateInput } from '../api/resources'
import { apiErrorMessage } from '../api/client'
import type { Agent, Branding } from '../api/types'
import { Button } from '../components/ui/Button'
import { ColorInput, Input, Select, Textarea } from '../components/ui/Field'
import { ErrorBanner, LoadingSpinner } from '../components/ui/Feedback'
import { useToast } from '../components/ui/Toast'
import { AgentBasicForm, type AgentBasicFormValue } from '../components/agents/AgentBasicForm'

type Tab = 'basic' | 'branding' | 'preview'

export function AgentDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { notify } = useToast()
  const [tab, setTab] = useState<Tab>('basic')
  const [agent, setAgent] = useState<Agent | null>(null)
  const [branding, setBranding] = useState<Branding | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [previewKey, setPreviewKey] = useState(0)

  async function load() {
    if (!id) return
    setLoading(true)
    setError(null)
    try {
      const [agentRes, brandingRes] = await Promise.all([agentsApi.get(id), agentsApi.getBranding(id)])
      setAgent(agentRes.data)
      setBranding(brandingRes.data)
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  async function saveBasic(updated: Partial<AgentCreateInput>) {
    if (!id) return
    try {
      const { data } = await agentsApi.update(id, updated)
      setAgent(data)
      notify('Agent updated')
    } catch (err) {
      notify(apiErrorMessage(err), 'error')
    }
  }

  async function saveBranding(updated: Partial<Branding>) {
    if (!id) return
    try {
      const { data } = await agentsApi.updateBranding(id, updated)
      setBranding(data)
      notify('Branding updated')
    } catch (err) {
      notify(apiErrorMessage(err), 'error')
    }
  }

  if (loading) return <LoadingSpinner />
  if (error) return <ErrorBanner message={error} />
  if (!agent || !branding || !id) return null

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">{agent.name}</h1>
        <p className="text-sm text-slate-500">{agent.company_name}</p>
      </div>

      <div className="flex gap-1 border-b border-slate-200">
        {(['basic', 'branding', 'preview'] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium capitalize ${
              tab === t ? 'border-b-2 border-brand-600 text-brand-600' : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {t === 'basic' ? 'Basic Info' : t === 'branding' ? 'Branding' : 'Preview & Embed'}
          </button>
        ))}
      </div>

      {tab === 'basic' && <BasicInfoTab agent={agent} onSave={saveBasic} />}
      {tab === 'branding' && (
        <BrandingTab agentId={id} branding={branding} onSave={saveBranding} onBrandingChange={setBranding} />
      )}
      {tab === 'preview' && (
        <PreviewTab agentId={id} previewKey={previewKey} onReload={() => setPreviewKey((k) => k + 1)} />
      )}
    </div>
  )
}

function agentToFormValue(agent: Agent): AgentBasicFormValue {
  return {
    name: agent.name,
    description: agent.description ?? '',
    displayName: agent.company_name,
    industry: agent.industry ?? '',
    languageRestriction: agent.languages.length === 0 ? 'none' : 'specific',
    restrictedLanguages: agent.languages,
    remarks: agent.remarks ?? '',
    notificationEmail: agent.notification_email ?? '',
  }
}

function BasicInfoTab({ agent, onSave }: { agent: Agent; onSave: (data: Partial<AgentCreateInput>) => void }) {
  const initial = agentToFormValue(agent)
  const [form, setForm] = useState(initial)

  return (
    <div className="max-w-2xl space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
      <AgentBasicForm value={form} onChange={setForm} />

      <div className="flex gap-2">
        <Button variant="secondary" onClick={() => setForm(initial)}>
          Cancel
        </Button>
        <Button
          onClick={() =>
            onSave({
              name: form.name,
              company_name: form.displayName,
              industry: form.industry || undefined,
              description: form.description || undefined,
              remarks: form.remarks || undefined,
              languages: form.languageRestriction === 'specific' ? form.restrictedLanguages : [],
              notification_email: form.notificationEmail || undefined,
            })
          }
        >
          Save Changes
        </Button>
      </div>
    </div>
  )
}

function BrandingTab({
  agentId,
  branding,
  onSave,
  onBrandingChange,
}: {
  agentId: string
  branding: Branding
  onSave: (data: Partial<Branding>) => void
  onBrandingChange: (b: Branding) => void
}) {
  const { notify } = useToast()
  const [form, setForm] = useState(branding)
  const [uploading, setUploading] = useState(false)

  async function handleLogoUpload(file: File) {
    setUploading(true)
    try {
      const { data } = await agentsApi.uploadLogo(agentId, file)
      onBrandingChange(data)
      setForm(data)
      notify('Logo uploaded')
    } catch (err) {
      notify(apiErrorMessage(err), 'error')
    } finally {
      setUploading(false)
    }
  }

  async function handleLogoDelete() {
    try {
      const { data } = await agentsApi.deleteLogo(agentId)
      onBrandingChange(data)
      setForm(data)
    } catch (err) {
      notify(apiErrorMessage(err), 'error')
    }
  }

  return (
    <div className="grid max-w-4xl gap-6 md:grid-cols-2">
      <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
        <div>
          <span className="mb-1 block text-sm font-medium text-slate-700">Company Logo</span>
          <div className="flex items-center gap-3">
            {form.logo_url && <img src={form.logo_url} alt="Logo" className="h-12 w-12 rounded-lg object-cover" />}
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp,image/svg+xml"
              disabled={uploading}
              onChange={(e) => e.target.files?.[0] && handleLogoUpload(e.target.files[0])}
              className="text-sm"
            />
            {form.logo_url && (
              <button className="text-xs text-red-600 hover:underline" onClick={handleLogoDelete}>
                Remove
              </button>
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <ColorInput
            label="Primary Color"
            value={form.primary_color}
            onChange={(v) => setForm({ ...form, primary_color: v })}
          />
          <ColorInput
            label="Secondary Color"
            value={form.secondary_color}
            onChange={(v) => setForm({ ...form, secondary_color: v })}
          />
          <ColorInput
            label="Background Color"
            value={form.background_color}
            onChange={(v) => setForm({ ...form, background_color: v })}
          />
          <ColorInput
            label="Text Color"
            value={form.text_color}
            onChange={(v) => setForm({ ...form, text_color: v })}
          />
          <ColorInput
            label="Button Color"
            value={form.button_color}
            onChange={(v) => setForm({ ...form, button_color: v })}
          />
        </div>

        <Input label="Font Family" value={form.font_family} onChange={(e) => setForm({ ...form, font_family: e.target.value })} />

        <div className="grid grid-cols-2 gap-4">
          <Select
            label="Widget Position"
            value={form.widget_position}
            onChange={(e) => setForm({ ...form, widget_position: e.target.value as Branding['widget_position'] })}
          >
            <option value="bottom_right">Bottom Right</option>
            <option value="bottom_left">Bottom Left</option>
          </Select>
          <Select
            label="Widget Size"
            value={form.widget_size}
            onChange={(e) => setForm({ ...form, widget_size: e.target.value as Branding['widget_size'] })}
          >
            <option value="compact">Compact</option>
            <option value="standard">Standard</option>
            <option value="large">Large</option>
          </Select>
        </div>

        <Textarea
          label="Welcome Message"
          value={form.welcome_message}
          onChange={(e) => setForm({ ...form, welcome_message: e.target.value })}
        />
        <Input
          label="Placeholder Text"
          value={form.placeholder_text}
          onChange={(e) => setForm({ ...form, placeholder_text: e.target.value })}
        />
        <Input
          label="Display Company Name"
          value={form.display_company_name ?? ''}
          onChange={(e) => setForm({ ...form, display_company_name: e.target.value })}
        />
        <Input
          label="Display Agent Name"
          value={form.display_agent_name ?? ''}
          onChange={(e) => setForm({ ...form, display_agent_name: e.target.value })}
        />

        <Button onClick={() => onSave(form)}>Save Branding</Button>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-5">
        <p className="mb-3 text-sm font-medium text-slate-700">Quick Preview</p>
        <div
          className="overflow-hidden rounded-xl border"
          style={{ backgroundColor: form.background_color, color: form.text_color, fontFamily: form.font_family }}
        >
          <div className="flex items-center gap-2 p-3" style={{ backgroundColor: form.primary_color, color: '#fff' }}>
            {form.logo_url && <img src={form.logo_url} className="h-6 w-6 rounded-full" alt="" />}
            <span className="text-sm font-semibold">{form.display_agent_name || 'Assistant'}</span>
          </div>
          <div className="space-y-2 p-3">
            <div className="max-w-[80%] rounded-lg bg-black/5 px-3 py-2 text-sm">{form.welcome_message}</div>
          </div>
          <div className="flex gap-2 border-t p-2">
            <div className="flex-1 rounded-full border px-3 py-1.5 text-xs text-slate-400">{form.placeholder_text}</div>
            <div className="rounded-full px-3 py-1.5 text-xs text-white" style={{ backgroundColor: form.button_color }}>
              Send
            </div>
          </div>
        </div>
        <p className="mt-2 text-xs text-slate-400">
          This is a static style preview. For the fully functional widget, use the "Preview &amp; Embed" tab.
        </p>
      </div>
    </div>
  )
}

function PreviewTab({ agentId, previewKey, onReload }: { agentId: string; previewKey: number; onReload: () => void }) {
  const { notify } = useToast()
  const [embedCode, setEmbedCode] = useState<string | null>(null)

  useEffect(() => {
    agentsApi.embedCode(agentId).then((res) => setEmbedCode(res.data.embed_code))
  }, [agentId])

  return (
    <div className="grid max-w-4xl gap-6 md:grid-cols-2">
      <div className="rounded-2xl border border-slate-200 bg-white p-5">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-sm font-medium text-slate-700">Live Widget Preview</p>
          <Button variant="secondary" onClick={onReload}>
            Reload
          </Button>
        </div>
        <iframe
          key={previewKey}
          title="Widget preview"
          src={`/widget-preview.html?agentId=${agentId}`}
          className="h-[480px] w-full rounded-lg border border-slate-200"
        />
        <p className="mt-2 text-xs text-slate-400">
          This runs the actual production widget script against saved branding — reload after saving changes.
        </p>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-5">
        <p className="mb-3 text-sm font-medium text-slate-700">Embed Code</p>
        {embedCode && (
          <div className="relative rounded-lg bg-slate-900 p-4">
            <pre className="overflow-x-auto text-xs text-slate-100">{embedCode}</pre>
            <button
              className="absolute right-2 top-2 rounded bg-slate-700 px-2 py-1 text-xs text-white hover:bg-slate-600"
              onClick={() => {
                navigator.clipboard.writeText(embedCode)
                notify('Embed code copied')
              }}
            >
              Copy
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
