import { useState } from 'react'
import { KeyRound, User as UserIcon } from 'lucide-react'
import { authApi } from '../api/resources'
import { apiErrorMessage } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Field'
import { ErrorBanner } from '../components/ui/Feedback'
import { useToast } from '../components/ui/Toast'

export function ProfilePage() {
  const { user, refreshUser } = useAuth()
  const { notify } = useToast()

  const [name, setName] = useState(user?.name ?? '')
  const [savingProfile, setSavingProfile] = useState(false)
  const [profileError, setProfileError] = useState<string | null>(null)

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [savingPassword, setSavingPassword] = useState(false)
  const [passwordError, setPasswordError] = useState<string | null>(null)

  if (!user) return null

  async function handleSaveProfile() {
    if (!name.trim()) return
    setSavingProfile(true)
    setProfileError(null)
    try {
      await authApi.updateProfile(name.trim())
      await refreshUser()
      notify('Profile updated')
    } catch (err) {
      setProfileError(apiErrorMessage(err))
    } finally {
      setSavingProfile(false)
    }
  }

  async function handleChangePassword() {
    setPasswordError(null)
    if (newPassword.length < 8) {
      setPasswordError('New password must be at least 8 characters.')
      return
    }
    if (newPassword !== confirmPassword) {
      setPasswordError('New password and confirmation do not match.')
      return
    }
    setSavingPassword(true)
    try {
      await authApi.changePassword(currentPassword, newPassword)
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      notify('Password changed')
    } catch (err) {
      setPasswordError(apiErrorMessage(err))
    } finally {
      setSavingPassword(false)
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-slate-900">My Profile</h1>
        <p className="mt-0.5 text-sm text-slate-500">Manage your account details and password.</p>
      </div>

      <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
          <UserIcon className="h-4 w-4 text-slate-400" />
          Account
        </div>

        {profileError && <ErrorBanner message={profileError} />}

        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Full name" value={name} onChange={(e) => setName(e.target.value)} />
          <div>
            <span className="mb-1 block text-sm font-medium text-slate-700">Email</span>
            <input
              value={user.email}
              disabled
              className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500"
            />
          </div>
        </div>

        <div>
          <span className="mb-1 block text-sm font-medium text-slate-700">Role</span>
          <Badge status={user.role} />
        </div>

        <div className="flex justify-end">
          <Button disabled={!name.trim() || savingProfile} onClick={handleSaveProfile}>
            {savingProfile ? 'Saving…' : 'Save changes'}
          </Button>
        </div>
      </div>

      <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
          <KeyRound className="h-4 w-4 text-slate-400" />
          Change Password
        </div>

        {passwordError && <ErrorBanner message={passwordError} />}

        <Input
          label="Current password"
          type="password"
          value={currentPassword}
          onChange={(e) => setCurrentPassword(e.target.value)}
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            label="New password"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
          />
          <Input
            label="Confirm new password"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
          />
        </div>

        <div className="flex justify-end">
          <Button
            disabled={!currentPassword || !newPassword || !confirmPassword || savingPassword}
            onClick={handleChangePassword}
          >
            {savingPassword ? 'Updating…' : 'Update password'}
          </Button>
        </div>
      </div>
    </div>
  )
}
