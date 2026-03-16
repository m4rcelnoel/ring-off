import { useEffect, useRef, useState } from 'react'
import { Settings, RefreshCw, Wifi, WifiOff, Bell, PersonStanding, Video, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Separator } from '@/components/ui/separator'
import CameraCard, { VideoPlayer } from '@/components/CameraCard'
import ChimeCard from '@/components/ChimeCard'
import EventsFeed from '@/components/EventsFeed'
import HAPanel from '@/components/HAPanel'
import RecordingsPanel from '@/components/RecordingsPanel'
import SettingsSheet from '@/components/SettingsSheet'
import { useEvents } from '@/hooks/useEvents'
import { api } from '@/lib/api'
import { APP_VERSION, APP_AUTHOR, APP_YEAR, APP_REPO } from '@/version'
import type { Camera, RingEvent } from '@/types'

type SidebarTab = 'events' | 'recordings' | 'ha'

interface Toast { id: string; event: RingEvent; camera?: Camera }

export default function Dashboard() {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [loadingCams, setLoadingCams] = useState(true)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [showLogin, setShowLogin] = useState(false)
  const [toasts, setToasts] = useState<Toast[]>([])
  const [expandedCamera, setExpandedCamera] = useState<Camera | null>(null)
  const [sidebarTab, setSidebarTab] = useState<SidebarTab>('events')
  const toastTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())

  const { events, deviceStates, connected } = useEvents((ev) => {
    const camera = cameras.find(c => c.id === ev.device_id || c.stream === ev.device_id || c.device_id === ev.device_id)
    const toast: Toast = { id: ev.id, event: ev, camera }
    setToasts(t => [toast, ...t].slice(0, 5))
    const timer = setTimeout(() => removeToast(ev.id), 5000)
    toastTimers.current.set(ev.id, timer)
  })

  const removeToast = (id: string) => {
    setToasts(t => t.filter(t => t.id !== id))
    const timer = toastTimers.current.get(id)
    if (timer) { clearTimeout(timer); toastTimers.current.delete(id) }
  }

  const loadCameras = async () => {
    setLoadingCams(true)
    try { setCameras(await api.get<Camera[]>('/api/cameras')) }
    finally { setLoadingCams(false) }
  }

  useEffect(() => { loadCameras() }, [])

  const cameraDeviceState = (camera: Camera) =>
    camera.device_id ? deviceStates[camera.device_id] : undefined

  const chimes = Object.values(deviceStates).filter(d => d.type === 'chime')

  return (
    <div className="flex h-screen flex-col">

      {/* Header */}
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-card/80 backdrop-blur px-4 lg:px-6">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10">
            <div className="h-3 w-3 rounded-full bg-primary" />
          </div>
          <span className="font-semibold text-base tracking-tight">Ring Off</span>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground mr-2">
            {connected
              ? <><Wifi className="h-3.5 w-3.5 text-emerald-400" /><span className="text-emerald-400">Live</span></>
              : <><WifiOff className="h-3.5 w-3.5" /><span>Offline</span></>
            }
          </div>
          <Button size="icon" variant="ghost" className="h-8 w-8" onClick={loadCameras} title="Refresh cameras">
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => setSettingsOpen(true)} title="Settings">
            <Settings className="h-4 w-4" />
          </Button>
        </div>
      </header>

      {/* Main layout */}
      <div className="flex flex-1 overflow-hidden">

        {/* Camera grid */}
        <main className="flex-1 overflow-y-auto p-4 lg:p-6">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-semibold text-sm text-muted-foreground uppercase tracking-widest">Cameras</h2>
            <span className="text-xs text-muted-foreground">{cameras.length} device{cameras.length !== 1 ? 's' : ''}</span>
          </div>

          {loadingCams ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <Skeleton className="aspect-video rounded-xl" />
              <Skeleton className="aspect-video rounded-xl" />
            </div>
          ) : cameras.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 text-muted-foreground gap-2">
              <span className="text-sm">No cameras found — is ring-mqtt running?</span>
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              {cameras.map(cam => (
                <CameraCard
                  key={cam.id}
                  camera={cam}
                  onExpand={setExpandedCamera}
                  deviceState={cameraDeviceState(cam)}
                />
              ))}
            </div>
          )}

          {/* Chimes section */}
          {chimes.length > 0 && (
            <div className="mt-8">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="font-semibold text-sm text-muted-foreground uppercase tracking-widest">Chimes</h2>
                <span className="text-xs text-muted-foreground">{chimes.length} device{chimes.length !== 1 ? 's' : ''}</span>
              </div>
              <div className="rounded-xl border border-border bg-card overflow-hidden">
                {chimes.map((chime) => (
                  <ChimeCard
                    key={chime.id}
                    deviceState={chime}
                    name={`Chime ${chime.id.slice(-4).toUpperCase()}`}
                  />
                ))}
              </div>
            </div>
          )}
        </main>

        {/* Sidebar */}
        <aside className="hidden lg:flex w-80 shrink-0 flex-col border-l border-border overflow-hidden">

          {/* Tab bar */}
          <div className="flex shrink-0 border-b border-border">
            {([
              { key: 'events',     label: 'Events',      icon: Bell },
              { key: 'recordings', label: 'Recordings',  icon: Video },
              { key: 'ha',         label: 'HA',          icon: null },
            ] as const).map(tab => (
              <button
                key={tab.key}
                onClick={() => setSidebarTab(tab.key)}
                className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2.5 text-xs font-medium transition-colors border-b-2 ${
                  sidebarTab === tab.key
                    ? 'border-primary text-foreground'
                    : 'border-transparent text-muted-foreground hover:text-foreground'
                }`}
              >
                {tab.icon && <tab.icon className="h-3.5 w-3.5" />}
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div className="flex-1 overflow-y-auto">
            {sidebarTab === 'events' && (
              <EventsFeed events={events} cameras={cameras} />
            )}
            {sidebarTab === 'recordings' && (
              <RecordingsPanel cameras={cameras} />
            )}
            {sidebarTab === 'ha' && (
              <HAPanel />
            )}
          </div>

          {/* Footer */}
          <div className="shrink-0 px-4 py-3 border-t border-border">
            <a href={APP_REPO} target="_blank" rel="noopener noreferrer"
              className="text-[10px] text-muted-foreground/50 hover:text-muted-foreground transition-colors block leading-relaxed">
              {APP_VERSION} · © {APP_YEAR} {APP_AUTHOR}
            </a>
            <p className="text-[10px] text-muted-foreground/30 leading-relaxed mt-0.5">
              Powered by ring-mqtt · go2rtc · FastAPI · React
            </p>
          </div>
        </aside>
      </div>

      {/* Camera fullscreen modal */}
      {expandedCamera && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 animate-fade-in"
          onClick={() => setExpandedCamera(null)}>
          <div className="w-full max-w-4xl rounded-xl overflow-hidden border border-border bg-black"
            onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-card">
              <span className="font-medium text-sm">{expandedCamera.name}</span>
              <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => setExpandedCamera(null)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
            <div className="aspect-video">
              <VideoPlayer streamName={expandedCamera.stream} />
            </div>
          </div>
        </div>
      )}

      {/* Toast notifications */}
      <div className="fixed bottom-4 right-4 z-40 flex flex-col gap-2 items-end">
        {toasts.map(t => {
          const isPerson = t.event.kind === 'motion' && t.event.person_detected
          return (
            <div key={t.id}
              className={`flex items-center gap-3 rounded-xl border px-4 py-3 shadow-2xl bg-card min-w-[240px] animate-fade-in cursor-pointer ${
                t.event.kind === 'motion' ? 'border-amber-500/30' : 'border-emerald-500/30'
              }`}
              onClick={() => removeToast(t.id)}>
              <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
                t.event.kind === 'motion' ? 'bg-amber-500/10 text-amber-400' : 'bg-emerald-500/10 text-emerald-400'
              }`}>
                {t.event.kind === 'motion' ? <PersonStanding className="h-4 w-4" /> : <Bell className="h-4 w-4" />}
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium">{t.camera?.name ?? t.event.device_id}</p>
                <p className="text-xs text-muted-foreground">
                  {t.event.kind === 'motion'
                    ? isPerson ? 'Person detected' : 'Motion detected'
                    : 'Doorbell rang'}
                </p>
              </div>
            </div>
          )
        })}
      </div>

      <SettingsSheet
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        onRelogin={() => setShowLogin(true)}
      />
    </div>
  )
}
