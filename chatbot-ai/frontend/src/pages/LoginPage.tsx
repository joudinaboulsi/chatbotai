import { useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { apiErrorMessage } from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Field'
import { ErrorBanner } from '../components/ui/Feedback'

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation() as { state?: { from?: { pathname: string } } }
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await login(email, password)
      navigate(location.state?.from?.pathname ?? '/dashboard', { replace: true })
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen">
      <div className="hidden w-1/2 flex-col justify-between bg-ink-950 p-10 text-white lg:flex">
        <div className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-500">
            <svg viewBox="0 0 24 24" className="h-5 w-5 text-white" fill="none">
              <path
                d="M12 3c-4.97 0-9 3.582-9 8 0 2.29 1.09 4.352 2.845 5.81-.096 1.02-.47 2.058-1.213 3.06-.14.19.008.453.24.42 1.79-.256 3.19-.856 4.24-1.55A10.6 10.6 0 0 0 12 19c4.97 0 9-3.582 9-8s-4.03-8-9-8Z"
                fill="currentColor"
              />
              <circle cx="8.5" cy="11" r="1.15" fill="#150f2e" />
              <circle cx="12" cy="11" r="1.15" fill="#150f2e" />
              <circle cx="15.5" cy="11" r="1.15" fill="#150f2e" />
            </svg>
          </span>
          <span className="text-sm font-semibold">AI Chatbot Platform</span>
        </div>
        <div className="max-w-sm">
          <span className="mb-3 inline-flex items-center rounded-full bg-accent-500/15 px-3 py-1 text-xs font-medium text-accent-300">
            Admin console
          </span>
          <h2 className="text-3xl font-semibold leading-tight">
            One console for every agent, conversation, and lead.
          </h2>
          <p className="mt-3 text-sm text-slate-300">
            Configure branding and knowledge bases, watch conversations in real time, and hand off to a live
            agent the moment a visitor needs one.
          </p>
        </div>
        <p className="text-xs text-slate-500">Admin panel · not a public sign-up</p>
      </div>

      <div className="flex flex-1 items-center justify-center bg-slate-50 px-4">
        <div className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
          <h1 className="text-xl font-semibold text-slate-900">Welcome back</h1>
          <p className="mt-1 text-sm text-slate-500">Sign in to the admin panel</p>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            {error && <ErrorBanner message={error} />}
            <Input
              label="Email"
              type="email"
              required
              autoFocus
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <Input
              label="Password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>
        </div>
      </div>
    </div>
  )
}
