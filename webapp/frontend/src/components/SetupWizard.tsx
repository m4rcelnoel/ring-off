import { useCallback, useEffect, useState } from 'react'
import {
  Check, X, Loader2, Circle, AlertTriangle, RefreshCw, Video, Bell,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import RingAuthForm from '@/components/RingAuthForm'
import { api } from '@/lib/api'
import type { Discovered, Preflight, PreflightCheck } from '@/types'

type Step = 'preflight' | 'ring' | 'discovery' | 'done'

const STEPS: { key: Step; label: string }[] = [
  { key: 'preflight', label: 'Checks' },
  { key: 'ring',      label: 'Ring account' },
  { key: 'discovery', label: 'Devices' },
  { key: 'done',      label: 'Finish' },
]

interface Props {
  onFinished: () => void
  ringAlreadyAuthenticated: boolean
}

export default function SetupWizard({ onFinished, ringAlreadyAuthenticated }: Props) {
  const [step, setStep] = useState<Step>(ringAlreadyAuthenticated ? 'discovery' : 'preflight')

  const finish = async () => {
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
          {step === 'discovery' && <DiscoveryStep onNext={() => setStep('done')} />}
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

// ── Step 4: finish ────────────────────────────────────────────────────────────

function DoneStep({ onFinish }: { onFinish: () => void }) {
  const [saving, setSaving] = useState(false)
  return (
    <div className="space-y-4 text-center">
      <div className="flex justify-center">
        <span className="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-400">
          <Check className="h-6 w-6" />
        </span>
      </div>
      <div>
        <h2 className="font-medium">You are set up</h2>
        <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
          Recording, notifications and a dashboard password can all be configured
          from the settings gear whenever you want them.
        </p>
      </div>
      <Button
        className="w-full"
        disabled={saving}
        onClick={async () => { setSaving(true); try { await onFinish() } finally { setSaving(false) } }}
      >
        {saving && <Loader2 className="h-4 w-4 animate-spin" />}
        Open the dashboard
      </Button>
    </div>
  )
}
