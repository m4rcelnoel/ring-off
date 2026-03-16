import { useState } from 'react'
import { Loader2, Circle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api } from '@/lib/api'

interface Props { onSuccess: () => void }

export default function LoginScreen({ onSuccess }: Props) {
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
      setError(err instanceof Error ? err.message : 'Verification failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-[radial-gradient(ellipse_at_50%_-20%,rgba(99,102,241,0.15),transparent_60%)]">
      <div className="w-full max-w-sm space-y-6">
        {/* Logo */}
        <div className="flex flex-col items-center gap-3">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 border border-primary/20">
            <Circle className="h-7 w-7 text-primary" strokeWidth={1.5} />
          </div>
          <div className="text-center">
            <h1 className="text-2xl font-semibold tracking-tight">Ring Off</h1>
            <p className="text-sm text-muted-foreground mt-1">
              {step === 'login' ? 'Sign in to your Ring account' : 'Enter your verification code'}
            </p>
          </div>
        </div>

        {/* Card */}
        <div className="rounded-xl border border-border bg-card p-6 shadow-2xl space-y-4">
          {step === 'login' ? (
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
            </form>
          ) : (
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
                onClick={() => { setStep('login'); setError('') }}>
                ← Back to login
              </Button>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
