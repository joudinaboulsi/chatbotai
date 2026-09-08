import { Input } from '../ui/Field'
import { INDUSTRY_OPTIONS, LANGUAGE_OPTIONS } from '../../lib/agentOptions'

export interface AgentBasicFormValue {
  name: string
  description: string
  displayName: string
  industry: string
  languageRestriction: 'none' | 'specific'
  restrictedLanguages: string[]
  remarks: string
  notificationEmail: string
}

export function AgentBasicForm({
  value,
  onChange,
}: {
  value: AgentBasicFormValue
  onChange: (value: AgentBasicFormValue) => void
}) {
  function set<K extends keyof AgentBasicFormValue>(key: K, val: AgentBasicFormValue[K]) {
    onChange({ ...value, [key]: val })
  }

  function toggleLanguage(code: string) {
    set(
      'restrictedLanguages',
      value.restrictedLanguages.includes(code)
        ? value.restrictedLanguages.filter((c) => c !== code)
        : [...value.restrictedLanguages, code],
    )
  }

  return (
    <div className="space-y-4">
      <div>
        <div className="mb-1 flex items-center justify-between">
          <span className="text-sm font-medium text-slate-700">
            Agent Name<span className="text-red-500">*</span>
          </span>
          <span className="text-xs text-slate-400">(For internal use)</span>
        </div>
        <input
          placeholder="Type here..."
          value={value.name}
          onChange={(e) => set('name', e.target.value)}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />
      </div>

      <div>
        <div className="mb-1 flex items-center justify-between">
          <span className="text-sm font-medium text-slate-700">Agent Description</span>
          <span className="text-xs text-slate-400">(For internal use)</span>
        </div>
        <textarea
          rows={3}
          placeholder="Describe your agent"
          value={value.description}
          onChange={(e) => set('description', e.target.value)}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="mb-1 flex items-center justify-between">
            <span className="text-sm font-medium text-slate-700">
              Display Name<span className="text-red-500">*</span>
            </span>
            <span className="text-xs text-slate-400">(For Public Use)</span>
          </div>
          <input
            placeholder="Type here..."
            value={value.displayName}
            onChange={(e) => set('displayName', e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        </div>
        <div>
          <span className="mb-1 block text-sm font-medium text-slate-700">
            Industry Type<span className="text-red-500">*</span>
          </span>
          <select
            value={value.industry}
            onChange={(e) => set('industry', e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          >
            <option value="">-Select-</option>
            {INDUSTRY_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <span className="mb-1 block text-sm font-medium text-slate-700">
          Language Restrictions<span className="text-red-500">*</span>
        </span>
        <p className="mb-2 text-xs text-slate-400">
          By default our agents can communicate in multiple languages. To restrict specific languages, select them
          from the drop-down below.
        </p>
        <select
          value={value.languageRestriction}
          onChange={(e) => set('languageRestriction', e.target.value as 'none' | 'specific')}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        >
          <option value="none">No Restrictions</option>
          <option value="specific">Restrict to Specific Languages</option>
        </select>
        {value.languageRestriction === 'specific' && (
          <div className="mt-2 flex flex-wrap gap-2">
            {LANGUAGE_OPTIONS.map((lang) => (
              <button
                type="button"
                key={lang.code}
                onClick={() => toggleLanguage(lang.code)}
                className={`rounded-full border px-3 py-1 text-xs ${
                  value.restrictedLanguages.includes(lang.code)
                    ? 'border-brand-600 bg-brand-50 text-brand-700'
                    : 'border-slate-300 text-slate-600'
                }`}
              >
                {lang.label}
              </button>
            ))}
          </div>
        )}
      </div>

      <div>
        <div className="mb-1 flex items-center justify-between">
          <span className="text-sm font-medium text-slate-700">Remarks</span>
          <span className="text-xs text-slate-400">(For internal use)</span>
        </div>
        <textarea
          rows={3}
          placeholder="Add here..."
          value={value.remarks}
          onChange={(e) => set('remarks', e.target.value)}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />
      </div>

      <Input
        label="Notification Email (for leads / handoff alerts)"
        type="email"
        value={value.notificationEmail}
        onChange={(e) => set('notificationEmail', e.target.value)}
      />
    </div>
  )
}
