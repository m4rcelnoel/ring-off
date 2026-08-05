import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api } from '@/lib/api'

interface Props {
  onSuccess: () => void
}

/** Ring OAuth sign-in with 2FA, shared by the standalone login and the wizard. */
export default function RingAuthForm({ onSuccess }: Props) {
  const [step, setStep] = useState<'login' | '2fa'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [sessionId, setSessionId] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true); setError('')
    try {
      const res = await api.post<{ success?: boolean; needs_2fa?: boolean; session_id?: string }>(
        '/api/auth/ring', { email, password }
      )
      if (res.needs_2fa && res.session_id) {
        setSessionId(res.session_id)
        setStep('2fa')
      } else if (res.success) {
        onSuccess()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  async function handleVerify(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true); setError('')
    try {
      await api.post('/api/auth/ring/verify', { session_id: sessionId, code })
      onSuccess()
    } catch (err) {
      // The session survives a failed code, so stay on this step and let the
      // user retry without re-entering their email and password.
      setError(err instanceof Error ? err.message : 'Verification failed')
    } finally {
      setLoading(false)
    }
  }

  if (step === 'login') {
    return (
      <form onSubmit={handleLogin} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" placeholder="you@example.com" value={email}
            onChange={e => setEmail(e.target.value)} required autoFocus />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input id="password" type="password" placeholder="••••••••" value={password}
            onChange={e => setPassword(e.target.value)} required />
        </div>
        {error && <p className="text-sm text-destructive bg-destructive/10 rounded-md px-3 py-2">{error}</p>}
        <Button type="submit" className="w-full" disabled={loading}>
          {loading && <Loader2 className="h-4 w-4 animate-spin" />}
          {loading ? 'Signing in…' : 'Sign In'}
        </Button>
        <p className="text-xs text-muted-foreground text-center">
          Your credentials go straight to Ring. Only the resulting token is stored, on this machine.
        </p>
      </form>
    )
  }

  return (
    <form onSubmit={handleVerify} className="space-y-4">
      <p className="text-sm text-muted-foreground text-center">
        Check your phone or authenticator app for the verification code
      </p>
      <div className="space-y-2">
        <Label htmlFor="code">Verification Code</Label>
        <Input id="code" type="text" inputMode="numeric" placeholder="123456"
          maxLength={6} value={code} onChange={e => setCode(e.target.value)}
          required autoFocus className="text-center text-lg tracking-widest" />
      </div>
      {error && <p className="text-sm text-destructive bg-destructive/10 rounded-md px-3 py-2">{error}</p>}
      <Button type="submit" className="w-full" disabled={loading}>
        {loading && <Loader2 className="h-4 w-4 animate-spin" />}
        {loading ? 'Verifying…' : 'Verify'}
      </Button>
      <Button type="button" variant="ghost" className="w-full text-muted-foreground"
        onClick={() => { setStep('login'); setError(''); setCode('') }}>
        ← Back to login
      </Button>
    </form>
  )
}
