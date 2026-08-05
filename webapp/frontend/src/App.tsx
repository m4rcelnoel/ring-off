import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type { AppStatus, SetupState } from '@/types'
import AppLogin from '@/components/AppLogin'
import SetupWizard from '@/components/SetupWizard'
import Dashboard from '@/components/Dashboard'

export default function App() {
  const [appStatus, setAppStatus] = useState<AppStatus | null>(null)
  const [setup, setSetup] = useState<SetupState | null>(null)

  useEffect(() => {
    api.get<AppStatus>('/api/app/status')
      .then(setAppStatus)
      .catch(() => setAppStatus({ auth_required: false, authenticated: true }))
  }, [])

  useEffect(() => {
    if (!appStatus?.authenticated) return
    api.get<SetupState>('/api/setup/state').then(setSetup).catch(console.error)
  }, [appStatus?.authenticated])

  // Waiting for initial auth check
  if (!appStatus) return null

  // App password required but not authenticated
  if (appStatus.auth_required && !appStatus.authenticated) {
    return (
      <AppLogin
        onSuccess={() => setAppStatus({ ...appStatus, authenticated: true })}
      />
    )
  }

  // Waiting for setup status
  if (!setup) return null

  // First run, or the user asked to run setup again. Installs that were already
  // working before the wizard existed are adopted on startup, so they land
  // straight on the dashboard.
  if (!setup.complete) {
    return (
      <SetupWizard
        ringAlreadyAuthenticated={setup.ring_authenticated}
        onFinished={() => setSetup({ ...setup, complete: true })}
      />
    )
  }

  return <Dashboard />
}
