import { useEffect, useRef, useState } from 'react'
import { Bell, PersonStanding, Footprints, Trash2, Play, RefreshCw, Video } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import type { Camera, Clip } from '@/types'

interface Props {
  cameras: Camera[]
}

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString(undefined, {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

interface VideoModalProps {
  clip: Clip
  cameraName: string
  onClose: () => void
}

function VideoModal({ clip, cameraName, onClose }: VideoModalProps) {
  return (
    <div
      className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-3xl rounded-xl overflow-hidden border border-border bg-black"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-card">
          <div>
            <span className="font-medium text-sm">{cameraName}</span>
            <span className="text-xs text-muted-foreground ml-2">{clip.filename}</span>
          </div>
          <Button size="sm" variant="ghost" onClick={onClose}>✕</Button>
        </div>
        <video
          src={`/recordings/files/${clip.path}`}
          controls
          autoPlay
          className="w-full aspect-video bg-black"
        />
      </div>
    </div>
  )
}

export default function RecordingsPanel({ cameras }: Props) {
  const [clips, setClips] = useState<Clip[]>([])
  const [loading, setLoading] = useState(true)
  const [playing, setPlaying] = useState<Clip | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)

  const cameraName = (device_id: string) =>
    cameras.find(c => c.device_id === device_id)?.name ?? device_id

  async function loadClips() {
    setLoading(true)
    try {
      const data = await api.get<Clip[]>('/api/recordings')
      setClips(data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadClips() }, [])

  async function deleteClip(clip: Clip) {
    const key = clip.path
    setDeleting(key)
    try {
      await api.delete(`/api/recordings/${clip.device_id}/${clip.filename}`)
      setClips(prev => prev.filter(c => c.path !== clip.path))
    } catch {
      // ignore
    } finally {
      setDeleting(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-40 text-muted-foreground text-sm">
        Loading recordings…
      </div>
    )
  }

  if (!clips.length) {
    return (
      <div className="flex flex-col items-center justify-center h-40 text-muted-foreground gap-2">
        <Video className="h-8 w-8 opacity-20" />
        <span className="text-sm">No recordings yet</span>
      </div>
    )
  }

  return (
    <>
      <div className="divide-y divide-border">
        {clips.map(clip => {
          const isPerson = clip.kind === 'motion' && clip.filename.includes('_motion')
          return (
            <div
              key={clip.path}
              className="flex items-center gap-3 px-4 py-3 hover:bg-accent/40 transition-colors group"
            >
              <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
                clip.kind === 'motion'
                  ? 'bg-amber-500/10 text-amber-400'
                  : 'bg-emerald-500/10 text-emerald-400'
              }`}>
                {clip.kind === 'ding'
                  ? <Bell className="h-4 w-4" />
                  : <Footprints className="h-4 w-4" />
                }
              </div>

              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{cameraName(clip.device_id)}</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {formatDate(clip.created)} · {formatBytes(clip.size)}
                </p>
              </div>

              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-7 w-7"
                  title="Play"
                  onClick={() => setPlaying(clip)}
                >
                  <Play className="h-3.5 w-3.5" />
                </Button>
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-7 w-7 text-destructive hover:text-destructive"
                  title="Delete"
                  disabled={deleting === clip.path}
                  onClick={() => deleteClip(clip)}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          )
        })}
      </div>

      {playing && (
        <VideoModal
          clip={playing}
          cameraName={cameraName(playing.device_id)}
          onClose={() => setPlaying(null)}
        />
      )}
    </>
  )
}
