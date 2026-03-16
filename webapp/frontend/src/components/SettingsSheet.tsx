import { useEffect, useState } from 'react'
import { Loader2, CheckCircle2 } from 'lucide-react'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import { api } from '@/lib/api'
import type { Settings } from '@/types'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  onRelogin: () => void
}

export default function SettingsSheet({ open, onOpenChange, onRelogin }: Props) {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [haUrl, setHaUrl] = useState('')
  const [haToken, setHaToken] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')
  const [pwSaving, setPwSaving] = useState(false)
  const [pwSaved, setPwSaved] = useState(false)

  useEffect(() => {
    if (!open) return
    api.get<Settings>('/api/settings').then(s => {
      setSettings(s)
      setHaUrl(s.ha_url)
    })
  }, [open])

  async function save() {
    if (!settings) return
    setSaving(true); setError(''); setSaved(false)
    try {
      await api.post('/api/settings', {
        ha_url:           haUrl,
        ha_token:         haToken || undefined,
        record_motion:    settings.record_motion,
        record_ding:      settings.record_ding,
        record_duration:  settings.record_duration,
        retention_days:   settings.retention_days,
        notify_url:       settings.notify_url,
        notify_on_motion: settings.notify_on_motion,
        notify_on_ding:   settings.notify_on_ding,
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  async function savePassword() {
    setPwSaving(true)
    try {
      await api.post('/api/app/set-password', { password: newPassword })
      setNewPassword('')
      setPwSaved(true)
      setTimeout(() => setPwSaved(false), 2000)
      if (settings) setSettings({ ...settings, app_password_set: Boolean(newPassword) })
    } finally {
      setPwSaving(false)
    }
  }

  const toggle = (key: 'record_motion' | 'record_ding' | 'notify_on_motion' | 'notify_on_ding', val: boolean) =>
    setSettings(s => s ? { ...s, [key]: val } : s)

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="overflow-y-auto">
        <SheetHeader>
          <SheetTitle>Settings</SheetTitle>
        </SheetHeader>

        <div className="px-6 pb-6 space-y-6 mt-2">

          {/* Ring Account */}
          <div className="space-y-3">
            <h3 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Ring Account</h3>
            <div className="flex items-center justify-between rounded-lg border border-border bg-accent/30 px-4 py-3">
              <div>
                <p className="text-sm font-medium">Status</p>
                <p className="text-xs text-muted-foreground mt-0.5">Token stored in ring-mqtt config</p>
              </div>
              <Badge variant="success">Connected</Badge>
            </div>
            <Button variant="outline" size="sm" className="w-full" onClick={() => { onOpenChange(false); onRelogin() }}>
              Re-authenticate with Ring
            </Button>
          </div>

          <Separator />

          {/* Recording */}
          <div className="space-y-4">
            <h3 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Video Recording</h3>
            <p className="text-xs text-muted-foreground">Automatically record a video clip when events occur</p>

            <div className="space-y-3">
              <div className="flex items-center justify-between rounded-lg border border-border px-4 py-3">
                <div>
                  <p className="text-sm font-medium">Record on Motion</p>
                  <p className="text-xs text-muted-foreground mt-0.5">Save a clip when motion is detected</p>
                </div>
                <Switch
                  checked={settings?.record_motion ?? true}
                  onCheckedChange={v => toggle('record_motion', v)}
                />
              </div>

              <div className="flex items-center justify-between rounded-lg border border-border px-4 py-3">
                <div>
                  <p className="text-sm font-medium">Record on Doorbell</p>
                  <p className="text-xs text-muted-foreground mt-0.5">Save a clip when the doorbell is pressed</p>
                </div>
                <Switch
                  checked={settings?.record_ding ?? true}
                  onCheckedChange={v => toggle('record_ding', v)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="duration">Clip Duration (seconds)</Label>
                <Input
                  id="duration"
                  type="number"
                  min={10}
                  max={300}
                  value={settings?.record_duration ?? 60}
                  onChange={e => setSettings(s => s ? { ...s, record_duration: parseInt(e.target.value) || 60 } : s)}
                />
                <p className="text-xs text-muted-foreground">How long to record after an event (10–300 s)</p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="retention">Clip Retention (days)</Label>
                <Input
                  id="retention"
                  type="number"
                  min={0}
                  value={settings?.retention_days ?? 30}
                  onChange={e => setSettings(s => s ? { ...s, retention_days: parseInt(e.target.value) || 0 } : s)}
                />
                <p className="text-xs text-muted-foreground">
                  Automatically delete recordings older than this many days. Set to 0 to keep forever.
                </p>
              </div>
            </div>
          </div>

          <Separator />

          {/* Notifications */}
          <div className="space-y-4">
            <h3 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Push Notifications</h3>
            <p className="text-xs text-muted-foreground">
              Send a push notification on events. Compatible with{' '}
              <span className="font-medium text-foreground">ntfy.sh</span> and{' '}
              <span className="font-medium text-foreground">Gotify</span>.
            </p>

            <div className="space-y-2">
              <Label htmlFor="notify-url">Notification URL</Label>
              <Input
                id="notify-url"
                type="url"
                placeholder="https://ntfy.sh/your-topic"
                value={settings?.notify_url ?? ''}
                onChange={e => setSettings(s => s ? { ...s, notify_url: e.target.value } : s)}
              />
              <p className="text-xs text-muted-foreground">
                ntfy.sh: <code className="text-foreground">https://ntfy.sh/your-topic</code>
                {' · '}Gotify: <code className="text-foreground">https://gotify.host/message?token=TOKEN</code>
              </p>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between rounded-lg border border-border px-4 py-3">
                <p className="text-sm font-medium">Notify on Motion</p>
                <Switch
                  checked={settings?.notify_on_motion ?? true}
                  onCheckedChange={v => toggle('notify_on_motion', v)}
                />
              </div>
              <div className="flex items-center justify-between rounded-lg border border-border px-4 py-3">
                <p className="text-sm font-medium">Notify on Doorbell</p>
                <Switch
                  checked={settings?.notify_on_ding ?? true}
                  onCheckedChange={v => toggle('notify_on_ding', v)}
                />
              </div>
            </div>
          </div>

          <Separator />

          {/* Home Assistant */}
          <div className="space-y-4">
            <h3 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Home Assistant</h3>

            <div className="space-y-2">
              <Label htmlFor="ha-url">URL</Label>
              <Input id="ha-url" type="url" placeholder="http://homeassistant.local:8123"
                value={haUrl} onChange={e => setHaUrl(e.target.value)} />
            </div>

            <div className="space-y-2">
              <Label htmlFor="ha-token">Long-Lived Access Token</Label>
              <Input id="ha-token" type="password"
                placeholder={settings?.ha_token_set ? '(saved — enter new to update)' : 'Paste token here'}
                value={haToken} onChange={e => setHaToken(e.target.value)} />
              <p className="text-xs text-muted-foreground">
                Create one in HA → Profile → Long-Lived Access Tokens
              </p>
            </div>
          </div>

          {error && (
            <p className="text-sm text-destructive bg-destructive/10 rounded-lg px-3 py-2">{error}</p>
          )}

          <Button className="w-full" onClick={save} disabled={saving}>
            {saving && <Loader2 className="h-4 w-4 animate-spin" />}
            {saved && <CheckCircle2 className="h-4 w-4 text-emerald-400" />}
            {saved ? 'Saved!' : saving ? 'Saving…' : 'Save Settings'}
          </Button>

          <Separator />

          {/* App Authentication */}
          <div className="space-y-4">
            <h3 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">App Access</h3>
            <p className="text-xs text-muted-foreground">
              Password-protect this dashboard. Leave blank to remove the password.
            </p>

            <div className="flex items-center justify-between rounded-lg border border-border bg-accent/30 px-4 py-3">
              <div>
                <p className="text-sm font-medium">Password Protection</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {settings?.app_password_set ? 'A password is set' : 'No password set'}
                </p>
              </div>
              <Badge variant={settings?.app_password_set ? 'success' : 'secondary'}>
                {settings?.app_password_set ? 'Enabled' : 'Disabled'}
              </Badge>
            </div>

            <div className="space-y-2">
              <Label htmlFor="app-password">New Password</Label>
              <Input
                id="app-password"
                type="password"
                placeholder={settings?.app_password_set ? '(enter new password to change)' : 'Set a password…'}
                value={newPassword}
                onChange={e => setNewPassword(e.target.value)}
              />
            </div>

            <Button variant="outline" className="w-full" onClick={savePassword} disabled={pwSaving}>
              {pwSaving && <Loader2 className="h-4 w-4 animate-spin" />}
              {pwSaved && <CheckCircle2 className="h-4 w-4 text-emerald-400" />}
              {pwSaved ? 'Saved!' : settings?.app_password_set ? 'Update Password' : 'Set Password'}
            </Button>
          </div>

        </div>
      </SheetContent>
    </Sheet>
  )
}
