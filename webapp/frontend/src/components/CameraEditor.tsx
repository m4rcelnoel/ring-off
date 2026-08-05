import { useEffect, useState } from 'react'
import { Loader2, Video, CheckCircle2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { api } from '@/lib/api'
import type { DiscoveredDevice } from '@/types'

interface Props {
  /** Called after a successful save — advances the wizard, or refreshes the dashboard. */
  onSaved?: () => void
  /** Wizards move on; the settings sheet stays put and shows a tick. */
  confirmInline?: boolean
}

/** Rename cameras and choose which appear, shared by setup and settings. */
export default function CameraEditor({ onSaved, confirmInline = false }: Props) {
  const [rows, setRows] = useState<DiscoveredDevice[] | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get<DiscoveredDevice[]>('/api/cameras/config')
      .then(setRows)
      .catch(() => setRows([]))
  }, [])

  const update = (deviceId: string, patch: Partial<DiscoveredDevice>) =>
    setRows(list => list?.map(r => (r.device_id === deviceId ? { ...r, ...patch } : r)) ?? null)

  async function save() {
    if (!rows) return
    setSaving(true); setError(''); setSaved(false)
    try {
      await api.post('/api/cameras/config', {
        cameras: rows.map(r => ({
          device_id: r.device_id,
          name: r.name,
          enabled: r.enabled !== false,
        })),
      })
      if (confirmInline) {
        setSaved(true)
        setTimeout(() => setSaved(false), 2000)
      }
      onSaved?.()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save')
    } finally {
      setSaving(false)
    }
  }

  if (!rows) {
    return (
      <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading cameras…
      </div>
    )
  }

  if (rows.length === 0) {
    return (
      <p className="text-sm text-muted-foreground text-center py-6">
        No cameras found yet. They appear here as ring-mqtt announces them.
      </p>
    )
  }

  const enabledCount = rows.filter(r => r.enabled !== false).length

  return (
    <div className="space-y-3">
      {rows.map(cam => {
        const on = cam.enabled !== false
        return (
          <div key={cam.device_id}
            className={`flex items-center gap-3 rounded-lg border border-border p-3 transition-opacity ${on ? '' : 'opacity-50'}`}>
            <div className="h-12 w-20 shrink-0 overflow-hidden rounded bg-black/40 flex items-center justify-center">
              {cam.has_snapshot ? (
                <img src={`/api/snapshot/${cam.device_id}`} alt=""
                  className="h-full w-full object-cover" />
              ) : (
                <Video className="h-4 w-4 text-muted-foreground" />
              )}
            </div>
            <div className="flex-1 min-w-0 space-y-1">
              <Input
                value={cam.name}
                disabled={!on}
                onChange={e => update(cam.device_id, { name: e.target.value })}
                placeholder="Front door"
                className="h-8"
              />
              <p className="text-[10px] text-muted-foreground truncate">
                {cam.device_id}
                {cam.battery_level != null && ` · ${cam.battery_level}% battery`}
              </p>
            </div>
            <Switch checked={on} onCheckedChange={v => update(cam.device_id, { enabled: v })} />
          </div>
        )
      })}

      {error && <p className="text-sm text-destructive bg-destructive/10 rounded-md px-3 py-2">{error}</p>}

      <Button onClick={save} disabled={saving} className="w-full"
        variant={confirmInline ? 'outline' : 'default'}>
        {saving && <Loader2 className="h-4 w-4 animate-spin" />}
        {saved && <CheckCircle2 className="h-4 w-4 text-emerald-400" />}
        {saved ? 'Saved!' : `Save ${enabledCount} camera${enabledCount !== 1 ? 's' : ''}`}
      </Button>
    </div>
  )
}
