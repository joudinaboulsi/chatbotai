import { useEffect, useState } from 'react'
import { settingsApi, smscSettingsApi } from '../api/resources'
import { apiErrorMessage } from '../api/client'
import type { EmailSettings, SMSCSettings, SmscAuthScheme, SmtpEncryption } from '../api/types'
import { Button } from '../components/ui/Button'
import { Input, Select } from '../components/ui/Field'
import { ErrorBanner, LoadingSpinner } from '../components/ui/Feedback'
import { useToast } from '../components/ui/Toast'

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
    <div className="max-w-xl space-y-6">
      <h1 className="text-xl font-semibold text-slate-900">Settings</h1>

      <SMSCSettingsSection />

      <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
        <h2 className="font-semibold text-slate-900">Email Configuration</h2>
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
        <Button disabled={saving} onClick={handleSave}>
          {saving ? 'Saving…' : 'Save Email Configuration'}
        </Button>
      </div>

      <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5">
        <h2 className="font-semibold text-slate-900">Test Email Configuration</h2>
        <Input label="Send test email to" type="email" value={testEmail} onChange={(e) => setTestEmail(e.target.value)} />
        <Button variant="secondary" disabled={testing || !settings.is_configured} onClick={handleTestEmail}>
          {testing ? 'Sending…' : 'Test Email Configuration'}
        </Button>
        {!settings.is_configured && (
          <p className="text-xs text-slate-500">Save a complete configuration (host, from email, support email) first.</p>
        )}
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

  return (
    <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
      <div>
        <h2 className="font-semibold text-slate-900">SMSC Integration</h2>
        <p className="text-xs text-slate-500">
          Lets the chatbot answer account-specific questions (balance, traffic, SMPP/HTTP API/HLR/DLR status, IP
          configuration) by calling the SMSC API after the visitor verifies their username. The chatbot never
          connects to the SMSC database directly.
        </p>
      </div>
      <Select
        label="Enabled"
        value={settings.enabled ? 'yes' : 'no'}
        onChange={(e) => setSettings({ ...settings, enabled: e.target.value === 'yes' })}
      >
        <option value="no">No</option>
        <option value="yes">Yes</option>
      </Select>
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
      <div className="flex items-center gap-3">
        <Button disabled={saving} onClick={handleSave}>
          {saving ? 'Saving…' : 'Save SMSC Configuration'}
        </Button>
        <Button variant="secondary" disabled={testing || !settings.is_configured} onClick={handleTest}>
          {testing ? 'Testing…' : 'Test Connection'}
        </Button>
      </div>
      {testResult && (
        <p className={`text-xs ${testResult.connected ? 'text-emerald-600' : 'text-red-600'}`}>{testResult.detail}</p>
      )}
      {!settings.is_configured && (
        <p className="text-xs text-slate-500">Save a base URL and credential first, then enable the integration.</p>
      )}
    </div>
  )
}
