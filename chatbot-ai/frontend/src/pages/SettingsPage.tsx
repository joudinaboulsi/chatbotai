import { useEffect, useState, type ReactNode } from 'react'
import { CheckCircle2, Mail, MessageSquareText, Send, XCircle, type LucideIcon } from 'lucide-react'
import { settingsApi, smscSettingsApi } from '../api/resources'
import { apiErrorMessage } from '../api/client'
import type { EmailSettings, SMSCSettings, SmscAuthScheme, SmtpEncryption } from '../api/types'
import { Button } from '../components/ui/Button'
import { Input, Select } from '../components/ui/Field'
import { ErrorBanner, LoadingSpinner } from '../components/ui/Feedback'
import { Switch } from '../components/ui/Switch'
import { useToast } from '../components/ui/Toast'

function StatusPill({ tone, children }: { tone: 'emerald' | 'amber' | 'slate'; children: ReactNode }) {
  const classes = {
    emerald: 'bg-emerald-100 text-emerald-700',
    amber: 'bg-amber-100 text-amber-700',
    slate: 'bg-slate-100 text-slate-600',
  }[tone]
  return <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${classes}`}>{children}</span>
}

function SectionCard({
  icon: Icon,
  iconTone,
  title,
  description,
  status,
  children,
}: {
  icon: LucideIcon
  iconTone: string
  title: string
  description?: string
  status?: ReactNode
  children: ReactNode
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${iconTone}`}>
            <Icon className="h-4.5 w-4.5" />
          </span>
          <div>
            <h2 className="font-semibold text-slate-900">{title}</h2>
            {description && <p className="mt-0.5 max-w-md text-xs leading-relaxed text-slate-500">{description}</p>}
          </div>
        </div>
        {status}
      </div>
      <div className="mt-5 space-y-4">{children}</div>
    </div>
  )
}

export function SettingsPage() {
  const { notify } = useToast()
  const [settings, setSettings] = useState<EmailSettings | null>(null)
  const [smtpPassword, setSmtpPassword] = useState('')
  const [testEmail, setTestEmail] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)

  useEffect(() => {
    settingsApi
      .getEmail()
      .then((res) => setSettings(res.data))
      .catch((err) => setError(apiErrorMessage(err)))
  }, [])

  async function handleSave() {
    if (!settings) return
    setSaving(true)
    try {
      const payload: Partial<EmailSettings> & { smtp_password?: string } = { ...settings }
      if (smtpPassword) payload.smtp_password = smtpPassword
      const { data } = await settingsApi.updateEmail(payload)
      setSettings(data)
      setSmtpPassword('')
      notify('Email settings saved')
    } catch (err) {
      notify(apiErrorMessage(err), 'error')
    } finally {
      setSaving(false)
    }
  }

  async function handleTestEmail() {
    if (!testEmail.trim()) return
    setTesting(true)
    try {
      await settingsApi.testEmail(testEmail.trim())
      notify('Test email sent successfully')
    } catch (err) {
      notify(apiErrorMessage(err), 'error')
    } finally {
      setTesting(false)
    }
  }

  if (error) return <ErrorBanner message={error} />
  if (!settings) return <LoadingSpinner />

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-slate-900">Settings</h1>
        <p className="mt-0.5 text-sm text-slate-500">Integrations and email delivery for this workspace</p>
      </div>

      <div className="grid items-start gap-6 lg:grid-cols-3">
        <SMSCSettingsSection />

        <SectionCard
          icon={Mail}
          iconTone="bg-brand-100 text-brand-700"
          title="Email Configuration"
          description="Used for lead notifications and any transactional email the platform sends."
          status={
            <StatusPill tone={settings.is_configured ? 'emerald' : 'slate'}>
              {settings.is_configured ? 'Configured' : 'Not configured'}
            </StatusPill>
          }
        >
          <Input
            label="SMTP Host"
            value={settings.smtp_host ?? ''}
            onChange={(e) => setSettings({ ...settings, smtp_host: e.target.value })}
          />
          <Input
            label="SMTP Port"
            type="number"
            value={settings.smtp_port}
            onChange={(e) => setSettings({ ...settings, smtp_port: Number(e.target.value) })}
          />
          <Input
            label="SMTP Username"
            value={settings.smtp_username ?? ''}
            onChange={(e) => setSettings({ ...settings, smtp_username: e.target.value })}
          />
          <Input
            label="SMTP Password"
            type="password"
            placeholder={settings.is_configured ? '••••••••  (leave blank to keep current)' : ''}
            value={smtpPassword}
            onChange={(e) => setSmtpPassword(e.target.value)}
          />
          <Select
            label="Encryption"
            value={settings.encryption}
            onChange={(e) => setSettings({ ...settings, encryption: e.target.value as SmtpEncryption })}
          >
            <option value="none">None</option>
            <option value="ssl">SSL</option>
            <option value="tls">TLS</option>
          </Select>
          <Input
            label="From Name"
            value={settings.from_name ?? ''}
            onChange={(e) => setSettings({ ...settings, from_name: e.target.value })}
          />
          <Input
            label="From Email"
            type="email"
            value={settings.from_email ?? ''}
            onChange={(e) => setSettings({ ...settings, from_email: e.target.value })}
          />
          <Input
            label="Support Email"
            type="email"
            value={settings.support_email ?? ''}
            onChange={(e) => setSettings({ ...settings, support_email: e.target.value })}
          />
          <div className="flex justify-end border-t border-slate-100 pt-4">
            <Button disabled={saving} onClick={handleSave}>
              {saving ? 'Saving…' : 'Save Email Configuration'}
            </Button>
          </div>
        </SectionCard>

        <SectionCard icon={Send} iconTone="bg-accent-100 text-accent-700" title="Test Email Configuration">
          <Input label="Send test email to" type="email" value={testEmail} onChange={(e) => setTestEmail(e.target.value)} />
          <Button
            variant="secondary"
            className="w-full"
            disabled={testing || !settings.is_configured}
            onClick={handleTestEmail}
          >
            {testing ? 'Sending…' : 'Send Test Email'}
          </Button>
          {!settings.is_configured && (
            <p className="text-xs text-slate-500">Save a complete configuration (host, from email, support email) first.</p>
          )}
        </SectionCard>
      </div>
    </div>
  )
}

function SMSCSettingsSection() {
  const { notify } = useToast()
  const [settings, setSettings] = useState<SMSCSettings | null>(null)
  const [apiKey, setApiKey] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ connected: boolean; detail: string } | null>(null)

  useEffect(() => {
    smscSettingsApi
      .get()
      .then((res) => setSettings(res.data))
      .catch((err) => setError(apiErrorMessage(err)))
  }, [])

  async function handleSave() {
    if (!settings) return
    setSaving(true)
    try {
      const payload: Partial<SMSCSettings> & { api_key?: string } = { ...settings }
      if (apiKey) payload.api_key = apiKey
      const { data } = await smscSettingsApi.update(payload)
      setSettings(data)
      setApiKey('')
      setTestResult(null)
      notify('SMSC integration settings saved')
    } catch (err) {
      notify(apiErrorMessage(err), 'error')
    } finally {
      setSaving(false)
    }
  }

  async function handleTest() {
    setTesting(true)
    setTestResult(null)
    try {
      const { data } = await smscSettingsApi.test()
      setTestResult(data)
    } catch (err) {
      notify(apiErrorMessage(err), 'error')
    } finally {
      setTesting(false)
    }
  }

  if (error) return <ErrorBanner message={error} />
  if (!settings) return <LoadingSpinner />

  const statusTone = !settings.is_configured ? 'slate' : settings.enabled ? 'emerald' : 'amber'
  const statusLabel = !settings.is_configured ? 'Not configured' : settings.enabled ? 'Enabled' : 'Configured, disabled'

  return (
    <SectionCard
      icon={MessageSquareText}
      iconTone="bg-brand-100 text-brand-700"
      title="SMSC Integration"
      description="Lets the chatbot answer account-specific questions (balance, traffic, SMPP/HTTP API/HLR/DLR status, IP configuration) by calling the SMSC API after the visitor verifies their username. The chatbot never connects to the SMSC database directly."
      status={<StatusPill tone={statusTone}>{statusLabel}</StatusPill>}
    >
      <div className="rounded-xl border border-slate-100 bg-slate-50 px-4 py-3">
        <Switch
          label="Enabled"
          description="Turn the integration on once a base URL and credential are saved."
          checked={settings.enabled}
          onChange={(value) => setSettings({ ...settings, enabled: value })}
        />
      </div>

      <Input
        label="API Base URL"
        placeholder="https://smsc-api.example.com"
        value={settings.api_base_url ?? ''}
        onChange={(e) => setSettings({ ...settings, api_base_url: e.target.value })}
      />

      <Select
        label="Authentication"
        value={settings.auth_scheme}
        onChange={(e) => setSettings({ ...settings, auth_scheme: e.target.value as SmscAuthScheme })}
      >
        <option value="bearer">Bearer Token</option>
        <option value="api_key">API Key</option>
      </Select>
      <Input
        label={settings.auth_scheme === 'bearer' ? 'Bearer Token' : 'API Key'}
        type="password"
        placeholder={settings.is_configured ? '••••••••  (leave blank to keep current)' : ''}
        value={apiKey}
        onChange={(e) => setApiKey(e.target.value)}
      />
      <Input
        label="Connection Timeout (seconds)"
        type="number"
        value={settings.timeout_seconds}
        onChange={(e) => setSettings({ ...settings, timeout_seconds: Number(e.target.value) })}
      />
      <Input
        label="Session Expiry (minutes)"
        type="number"
        value={settings.session_expire_minutes}
        onChange={(e) => setSettings({ ...settings, session_expire_minutes: Number(e.target.value) })}
      />

      <div className="space-y-3 border-t border-slate-100 pt-4">
        <div className="flex items-center gap-3">
          <Button disabled={saving} onClick={handleSave}>
            {saving ? 'Saving…' : 'Save'}
          </Button>
          <Button variant="secondary" disabled={testing || !settings.is_configured} onClick={handleTest}>
            {testing ? 'Testing…' : 'Test Connection'}
          </Button>
        </div>
        {testResult && (
          <span
            className={`inline-flex items-center gap-1.5 text-xs font-medium ${
              testResult.connected ? 'text-emerald-600' : 'text-red-600'
            }`}
          >
            {testResult.connected ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
            {testResult.detail}
          </span>
        )}
      </div>
      {!settings.is_configured && (
        <p className="text-xs text-slate-500">Save a base URL and credential first, then enable the integration.</p>
      )}
    </SectionCard>
  )
}
