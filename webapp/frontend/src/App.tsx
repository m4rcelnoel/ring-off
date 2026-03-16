import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type { AppStatus, Status } from '@/types'
import AppLogin from '@/components/AppLogin'
import LoginScreen from '@/components/LoginScreen'
import Dashboard from '@/components/Dashboard'

export default function App() {
  const [appStatus, setAppStatus] = useState<AppStatus | null>(null)
  const [status, setStatus] = useState<Status | null>(null)

  useEffect(() => {
    api.get<AppStatus>('/api/app/status')
      .then(setAppStatus)
      .catch(() => setAppStatus({ auth_required: false, authenticated: true }))
  }, [])

  useEffect(() => {
    if (!appStatus?.authenticated) return
    api.get<Status>('/api/status').then(setStatus).catch(console.error)
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

  // Waiting for Ring config status
  if (!status) return null

  // Ring not configured — show login
  if (!status.ring_configured) {
    return (
      <LoginScreen
        onSuccess={() => setStatus({ ...status, ring_configured: true })}
      />
    )
  }

  return <Dashboard />
}
