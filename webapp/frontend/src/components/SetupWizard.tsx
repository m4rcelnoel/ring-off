import { useCallback, useEffect, useState } from 'react'
import {
  Check, X, Loader2, Circle, AlertTriangle, RefreshCw, Video, Bell,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import RingAuthForm from '@/components/RingAuthForm'
import CameraEditor from '@/components/CameraEditor'
import { api } from '@/lib/api'
import type { Discovered, Preflight, PreflightCheck, Settings } from '@/types'

type Step = 'preflight' | 'ring' | 'discovery' | 'cameras' | 'alerts' | 'done'

const STEPS: { key: Step; label: string }[] = [
  { key: 'preflight', label: 'Checks' },
  { key: 'ring',      label: 'Ring' },
  { key: 'discovery', label: 'Devices' },
  { key: 'cameras',   label: 'Cameras' },
  { key: 'alerts',    label: 'Alerts' },
  { key: 'done',      label: 'Finish' },
]

interface Props {
  onFinished: () => void
  ringAlreadyAuthenticated: boolean
}

export default function SetupWizard({ onFinished, ringAlreadyAuthenticated }: Props) {
  const [step, setStep] = useState<Step>(ringAlreadyAuthenticated ? 'discovery' : 'preflight')

  const finish = async (password: string) => {
    if (password) {
      await api.post('/api/app/set-password', { password })
      // Log straight in, otherwise the very next request is blocked by the
      // password we just set and setup can never be marked complete.
      await api.post('/api/app/login', { password })
    }
    await api.post('/api/setup/complete', {})
    onFinished()
  }

  const stepIndex = STEPS.findIndex(s => s.key === step)

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-[radial-gradient(ellipse_at_50%_-20%,rgba(99,102,241,0.15),transparent_60%)]">
      <div className="w-full max-w-lg space-y-6">

        <div className="flex flex-col items-center gap-3">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 border border-primary/20">
            <Circle className="h-7 w-7 text-primary" strokeWidth={1.5} />
          </div>
          <div className="text-center">
            <h1 className="text-2xl font-semibold tracking-tight">Set up Ring Off</h1>
            <p className="text-sm text-muted-foreground mt-1">
              A few steps and your cameras are live. Nothing leaves your network.
            </p>
          </div>
        </div>

        {/* Step indicator */}
        <ol className="flex items-center justify-center gap-2">
          {STEPS.map((s, i) => (
            <li key={s.key} className="flex items-center gap-2">
              <span className={`flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-medium transition-colors ${
                i < stepIndex ? 'bg-primary/20 text-primary'
                  : i === stepIndex ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-muted-foreground'
              }`}>
                {i < stepIndex ? <Check className="h-3 w-3" /> : i + 1}
              </span>
              <span className={`text-xs ${i === stepIndex ? 'text-foreground' : 'text-muted-foreground'}`}>
                {s.label}
              </span>
              {i < STEPS.length - 1 && <span className="w-4 h-px bg-border" />}
            </li>
          ))}
        </ol>

        <div className="rounded-xl border border-border bg-card p-6 shadow-2xl">
          {step === 'preflight' && <PreflightStep onNext={() => setStep('ring')} />}
          {step === 'ring' && <RingStep onNext={() => setStep('discovery')} />}
          {step === 'discovery' && <DiscoveryStep onNext={() => setStep('cameras')} />}
          {step === 'cameras' && <CameraStep onNext={() => setStep('alerts')} />}
          {step === 'alerts' && <AlertsStep onNext={() => setStep('done')} />}
          {step === 'done' && <DoneStep onFinish={finish} />}
        </div>
      </div>
    </div>
  )
}

// ── Step 1: preflight ─────────────────────────────────────────────────────────

function CheckRow({ check }: { check: PreflightCheck }) {
  const failedButOptional = !check.ok && !check.required
  return (
    <div className="rounded-lg border border-border px-4 py-3">
      <div className="flex items-center gap-3">
        <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full ${
          check.ok ? 'bg-emerald-500/10 text-emerald-400'
            : failedButOptional ? 'bg-amber-500/10 text-amber-400'
            : 'bg-destructive/10 text-destructive'
        }`}>
          {check.ok ? <Check className="h-3 w-3" />
            : failedButOptional ? <AlertTriangle className="h-3 w-3" />
            : <X className="h-3 w-3" />}
        </span>
        <span className="text-sm font-medium flex-1">{check.label}</span>
        {failedButOptional && <span className="text-[10px] uppercase tracking-wide text-amber-400">optional</span>}
      </div>
      {check.hint && <p className="text-xs text-muted-foreground mt-2 pl-8 leading-relaxed">{check.hint}</p>}
    </div>
  )
}

function PreflightStep({ onNext }: { onNext: () => void }) {
  const [result, setResult] = useState<Preflight | null>(null)
  const [checking, setChecking] = useState(false)

  const run = useCallback(async () => {
    setChecking(true)
    try { setResult(await api.get<Preflight>('/api/setup/preflight')) }
    finally { setChecking(false) }
  }, [])

  useEffect(() => { run() }, [run])

  if (!result) {
    return (
      <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Checking your stack…
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="font-medium">Service checks</h2>
        <p className="text-xs text-muted-foreground mt-1">
          Everything the setup needs. Optional failures will not block you.
        </p>
      </div>
      <div className="space-y-2">
        {result.checks.map(c => <CheckRow key={c.key} check={c} />)}
      </div>
      <div className="flex gap-2">
        <Button variant="outline" onClick={run} disabled={checking} className="flex-1">
          {checking ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          Re-check
        </Button>
        <Button onClick={onNext} disabled={!result.ok} className="flex-1">Continue</Button>
      </div>
      {!result.ok && (
        <p className="text-xs text-muted-foreground text-center">
          Fix the failures above, then re-check. Setup cannot continue without them.
        </p>
      )}
    </div>
  )
}

// ── Step 2: Ring account ──────────────────────────────────────────────────────

function RingStep({ onNext }: { onNext: () => void }) {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="font-medium">Sign in to Ring</h2>
        <p className="text-xs text-muted-foreground mt-1">
          This stores a token so ring-mqtt can talk to your devices. No subscription needed.
        </p>
      </div>
      <RingAuthForm onSuccess={onNext} />
    </div>
  )
}

// ── Step 3: discovery ─────────────────────────────────────────────────────────

function DiscoveryStep({ onNext }: { onNext: () => void }) {
  const [found, setFound] = useState<Discovered | null>(null)
  const [waited, setWaited] = useState(0)

  useEffect(() => {
    let cancelled = false
    const poll = async () => {
      try {
        const data = await api.get<Discovered>('/api/setup/discovered')
        if (!cancelled) setFound(data)
      } catch { /* keep polling — ring-mqtt is probably still restarting */ }
    }
    poll()
    const timer = setInterval(() => { setWaited(w => w + 2); poll() }, 2000)
    return () => { cancelled = true; clearInterval(timer) }
  }, [])

  const cameras = found?.cameras ?? []
  const chimes = found?.chimes ?? []
  const nothingYet = cameras.length === 0 && chimes.length === 0

  return (
    <div className="space-y-4">
      <div>
        <h2 className="font-medium">Finding your devices</h2>
        <p className="text-xs text-muted-foreground mt-1">
          ring-mqtt is connecting to Ring and announcing devices over MQTT.
        </p>
      </div>

      {nothingYet ? (
        <div className="flex flex-col items-center justify-center gap-3 py-8 text-center">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Waiting for the first device…</p>
          {waited >= 60 && (
            <p className="text-xs text-amber-400 max-w-xs leading-relaxed">
              Still nothing after a minute. Check <code>docker compose logs ring-mqtt</code> —
              an expired or rejected token is the usual cause.
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          {cameras.map(d => (
            <div key={d.device_id} className="flex items-center gap-3 rounded-lg border border-border px-4 py-3">
              <Video className="h-4 w-4 text-primary shrink-0" />
              <span className="text-sm font-medium flex-1">{d.name}</span>
              {d.battery_level != null && (
                <span className="text-xs text-muted-foreground">{d.battery_level}%</span>
              )}
            </div>
          ))}
          {chimes.map(d => (
            <div key={d.device_id} className="flex items-center gap-3 rounded-lg border border-border px-4 py-3">
              <Bell className="h-4 w-4 text-muted-foreground shrink-0" />
              <span className="text-sm font-medium flex-1">{d.name}</span>
            </div>
          ))}
          <p className="text-xs text-muted-foreground pt-1">
            {cameras.length} camera{cameras.length !== 1 ? 's' : ''}
            {chimes.length > 0 && `, ${chimes.length} chime${chimes.length !== 1 ? 's' : ''}`} found.
            Cameras are added to go2rtc automatically.
          </p>
        </div>
      )}

      <Button onClick={onNext} className="w-full" disabled={nothingYet}>Continue</Button>
    </div>
  )
}

// ── Step 4: name the cameras ──────────────────────────────────────────────────

function CameraStep({ onNext }: { onNext: () => void }) {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="font-medium">Name your cameras</h2>
        <p className="text-xs text-muted-foreground mt-1">
          Give each one a name you will recognise. Switch off any you do not want on the dashboard.
          You can change all of this later in Settings.
        </p>
      </div>
      <CameraEditor onSaved={onNext} />
    </div>
  )
}

// ── Step 5: recording and alerts ──────────────────────────────────────────────

function AlertsStep({ onNext }: { onNext: () => void }) {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; detail: string } | null>(null)

  useEffect(() => { api.get<Settings>('/api/settings').then(setSettings) }, [])

  const patch = (change: Partial<Settings>) =>
    setSettings(s => (s ? { ...s, ...change } : s))

  async function test() {
    setTesting(true); setTestResult(null)
    try {
      setTestResult(await api.post<{ ok: boolean; detail: string }>(
        '/api/setup/test-notification', { notify_url: settings?.notify_url ?? '' }))
    } catch (e) {
      setTestResult({ ok: false, detail: e instanceof Error ? e.message : 'Failed' })
    } finally {
      setTesting(false)
    }
  }

  async function save() {
    if (!settings) return
    setSaving(true)
    try {
      await api.post('/api/settings', {
        ha_url: settings.ha_url,
        record_motion: settings.record_motion,
        record_ding: settings.record_ding,
        record_duration: settings.record_duration,
        retention_days: settings.retention_days,
        notify_url: settings.notify_url,
        notify_on_motion: settings.notify_on_motion,
        notify_on_ding: settings.notify_on_ding,
        notify_on_low_battery: settings.notify_on_low_battery,
        low_battery_threshold: settings.low_battery_threshold,
        notify_on_connection_lost: settings.notify_on_connection_lost,
      })
      onNext()
    } finally {
      setSaving(false)
    }
  }

  if (!settings) {
    return (
      <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading…
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="font-medium">Recording and alerts</h2>
        <p className="text-xs text-muted-foreground mt-1">
          All optional, and all changeable later in Settings.
        </p>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between rounded-lg border border-border px-4 py-3">
          <div>
            <p className="text-sm font-medium">Record on motion</p>
            <p className="text-xs text-muted-foreground mt-0.5">Save a clip when motion is detected</p>
          </div>
          <Switch checked={settings.record_motion}
            onCheckedChange={v => patch({ record_motion: v })} />
        </div>
        <div className="flex items-center justify-between rounded-lg border border-border px-4 py-3">
          <div>
            <p className="text-sm font-medium">Record on doorbell</p>
            <p className="text-xs text-muted-foreground mt-0.5">Save a clip when the doorbell is pressed</p>
          </div>
          <Switch checked={settings.record_ding}
            onCheckedChange={v => patch({ record_ding: v })} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="w-duration" className="text-xs">Clip length (s)</Label>
          <Input id="w-duration" type="number" min={10} max={300} className="h-8"
            value={settings.record_duration}
            onChange={e => patch({ record_duration: parseInt(e.target.value) || 60 })} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="w-retention" className="text-xs">Keep for (days)</Label>
          <Input id="w-retention" type="number" min={0} className="h-8"
            value={settings.retention_days}
            onChange={e => patch({ retention_days: parseInt(e.target.value) || 0 })} />
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="w-notify" className="text-xs">Notification URL (optional)</Label>
        <Input id="w-notify" type="url" placeholder="https://ntfy.sh/your-topic" className="h-8"
          value={settings.notify_url}
          onChange={e => { patch({ notify_url: e.target.value }); setTestResult(null) }} />
        <p className="text-[10px] text-muted-foreground">
          ntfy.sh or Gotify. Push alerts for motion, doorbell, low battery and devices going offline.
        </p>
        <Button type="button" variant="outline" size="sm" className="w-full"
          disabled={testing || !settings.notify_url} onClick={test}>
          {testing && <Loader2 className="h-4 w-4 animate-spin" />}
          Send a test notification
        </Button>
        {testResult && (
          <p className={`text-xs rounded-md px-3 py-2 ${
            testResult.ok ? 'text-emerald-400 bg-emerald-500/10' : 'text-destructive bg-destructive/10'
          }`}>
            {testResult.ok ? 'Sent — check your device.' : testResult.detail}
          </p>
        )}
      </div>

      <Button onClick={save} disabled={saving} className="w-full">
        {saving && <Loader2 className="h-4 w-4 animate-spin" />}
        Continue
      </Button>
    </div>
  )
}

// ── Step 6: password and finish ───────────────────────────────────────────────

function DoneStep({ onFinish }: { onFinish: (password: string) => Promise<void> }) {
  const [password, setPassword] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function done() {
    setSaving(true); setError('')
    try {
      await onFinish(password)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not finish setup')
      setSaving(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-center">
        <span className="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-400">
          <Check className="h-6 w-6" />
        </span>
      </div>
      <div className="text-center">
        <h2 className="font-medium">Almost there</h2>
        <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
          Protect the dashboard with a password. Anyone who can reach this server
          can otherwise watch your cameras and recordings.
        </p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="w-password" className="text-xs">Dashboard password (optional)</Label>
        <Input id="w-password" type="password" placeholder="Leave blank to skip" className="h-8"
          value={password} onChange={e => setPassword(e.target.value)} />
      </div>

      {error && <p className="text-sm text-destructive bg-destructive/10 rounded-md px-3 py-2">{error}</p>}

      <Button className="w-full" disabled={saving} onClick={done}>
        {saving && <Loader2 className="h-4 w-4 animate-spin" />}
        {password ? 'Set password and open the dashboard' : 'Open the dashboard'}
      </Button>
    </div>
  )
}
