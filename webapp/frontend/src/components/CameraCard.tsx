import { useEffect, useRef, useState } from 'react'
import { Loader2, Maximize2, Play, VideoOff, BatteryLow, Wifi } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useVideoRtc } from '@/hooks/useVideoRtc'
import { reportAspect, useAspect } from '@/lib/aspect'
import type { Camera, DeviceState } from '@/types'

// Tell TypeScript about the go2rtc custom element
declare global {
  namespace JSX {
    interface IntrinsicElements {
      'video-rtc': React.DetailedHTMLProps<
        React.HTMLAttributes<HTMLElement> & { src?: string },
        HTMLElement
      >
    }
  }
}

interface Props {
  camera: Camera
  onExpand: (camera: Camera) => void
  deviceState?: DeviceState
}

export function VideoPlayer({ streamName, mode: initialMode = 'webrtc' }: {
  streamName: string
  mode?: 'webrtc' | 'mjpeg'
}) {
  const rtcState = useVideoRtc()
  const rtcReady = rtcState === 'ready'
  const [mode, setMode] = useState<'webrtc' | 'mjpeg'>(initialMode)
  const playerRef = useRef<HTMLElement | null>(null)

  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${proto}//${location.host}/ws/video?src=${streamName}`

  // `src` must be assigned as a *property*, not a JSX attribute. VideoRTC starts
  // the connection from its `set src()` accessor and defines no
  // attributeChangedCallback, while React 18 writes unknown custom-element props
  // as attributes — so the setter never ran, wsURL stayed undefined, and
  // onconnect() returned early every time, leaving the player permanently black.
  useEffect(() => {
    const el = playerRef.current as (HTMLElement & { src?: string }) | null
    if (el) el.src = wsUrl
  }, [wsUrl, rtcReady, mode])

  // The live picture is the authority on the camera's shape; 'resize' also
  // fires when a camera switches resolution mid-stream.
  useEffect(() => {
    const video = playerRef.current?.querySelector('video')
    if (!video) return
    const update = () => reportAspect(streamName, video.videoWidth, video.videoHeight)
    update()
    video.addEventListener('resize', update)
    video.addEventListener('loadedmetadata', update)
    return () => {
      video.removeEventListener('resize', update)
      video.removeEventListener('loadedmetadata', update)
    }
  }, [streamName, rtcReady, mode])

  if (mode === 'webrtc' && rtcReady) {
    return (
      <div className="relative w-full h-full">
        {/* eslint-disable-next-line @typescript-eslint/ban-ts-comment */}
        {/* @ts-ignore */}
        <video-rtc
          ref={playerRef}
          style={{ width: '100%', height: '100%', display: 'block' }}
        />
        <button
          className="absolute bottom-2 right-2 text-[10px] text-white/50 hover:text-white/80 bg-black/50 rounded px-1.5 py-0.5 transition-colors"
          title="Switch to MJPEG fallback"
          onClick={() => setMode('mjpeg')}
        >
          MJPEG
        </button>
      </div>
    )
  }

  if (mode === 'webrtc' && rtcState === 'loading') {
    return (
      <div className="w-full h-full flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-white/40" />
      </div>
    )
  }

  return <MjpegStream streamName={streamName} />
}

// A 1×1 transparent GIF, used to abort the MJPEG request on unmount.
const BLANK_IMAGE = 'data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw=='

/**
 * Chrome keeps a multipart/x-mixed-replace image downloading after the <img>
 * leaves the DOM. Each one is an ffmpeg process in the backend holding the Ring
 * livestream open — so "Stop" left the doorbell streaming (and draining its
 * battery). Pointing src elsewhere before unmount aborts the request.
 */
function MjpegStream({ streamName }: { streamName: string }) {
  const imgRef = useRef<HTMLImageElement | null>(null)

  useEffect(() => {
    const img = imgRef.current
    return () => { if (img) img.src = BLANK_IMAGE }
  }, [streamName])

  return (
    <img
      ref={imgRef}
      src={`/stream/${streamName}`}
      className="w-full h-full object-cover"
      alt={streamName}
    />
  )
}

function BatteryIndicator({ level }: { level: number }) {
  const color = level <= 20 ? 'text-red-400' : level <= 40 ? 'text-amber-400' : 'text-emerald-400'
  return (
    <span className={`flex items-center gap-1 text-[10px] font-medium ${color}`}>
      <BatteryLow className="h-3 w-3" />
      {level}%
    </span>
  )
}

function WifiIndicator({ signal }: { signal: number }) {
  const color = signal >= -60 ? 'text-emerald-400' : signal >= -75 ? 'text-amber-400' : 'text-red-400'
  return (
    <span className={`flex items-center gap-1 text-[10px] font-medium ${color}`} title={`${signal} dBm`}>
      <Wifi className="h-3 w-3" />
      {signal} dBm
    </span>
  )
}

export default function CameraCard({ camera, onExpand, deviceState }: Props) {
  const [active, setActive] = useState(false)
  const [snapshotOk, setSnapshotOk] = useState(true)
  const aspect = useAspect(camera.stream)

  // Only request a snapshot the backend actually has cached. Requesting one
  // unconditionally makes every card without a snapshot log a 404 (PR #1).
  const snapshotUrl = camera.device_id && camera.has_snapshot && snapshotOk
    ? `/api/snapshot/${camera.device_id}`
    : null

  return (
    <div className="group relative rounded-xl border border-border bg-card overflow-hidden hover:border-primary/50 transition-colors">
      {/* Video area */}
      <div className="relative bg-black" style={{ aspectRatio: aspect }}>
        {active ? (
          <VideoPlayer streamName={camera.stream} />
        ) : (
          <button
            className="relative w-full h-full flex flex-col items-center justify-center gap-3"
            onClick={() => setActive(true)}
          >
            {snapshotUrl ? (
              <>
                <img
                  src={snapshotUrl}
                  className="absolute inset-0 w-full h-full object-cover opacity-70"
                  alt="snapshot"
                  onLoad={e => reportAspect(camera.stream,
                    e.currentTarget.naturalWidth, e.currentTarget.naturalHeight)}
                  onError={() => setSnapshotOk(false)}
                />
                <div className="relative flex flex-col items-center gap-2 text-white drop-shadow">
                  <div className="h-10 w-10 rounded-full bg-black/60 flex items-center justify-center">
                    <Play className="h-5 w-5 translate-x-px" />
                  </div>
                  <span className="text-xs font-medium bg-black/40 rounded px-2 py-0.5">
                    Click to start stream
                  </span>
                </div>
              </>
            ) : (
              <>
                <VideoOff className="h-10 w-10 opacity-30 text-muted-foreground" />
                <span className="text-xs text-muted-foreground">Click to start stream</span>
              </>
            )}
          </button>
        )}

        {/* Expand button */}
        <Button
          size="icon"
          variant="secondary"
          className="absolute top-2 right-2 h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity bg-black/60 hover:bg-black/80 border-0"
          onClick={() => onExpand(camera)}
        >
          <Maximize2 className="h-3.5 w-3.5" />
        </Button>

        {/* Live indicator */}
        {active && (
          <div className="absolute top-2 left-2 flex items-center gap-1.5 rounded-full bg-black/60 px-2 py-1">
            <span className="h-1.5 w-1.5 rounded-full bg-red-500 animate-pulse" />
            <span className="text-[10px] font-medium text-white uppercase tracking-wider">Live</span>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between px-4 py-3">
        <div>
          <p className="font-medium text-sm">{camera.name}</p>
          <div className="flex items-center gap-3 mt-1">
            {deviceState?.battery_level != null && (
              <BatteryIndicator level={deviceState.battery_level} />
            )}
            {deviceState?.wifi_signal != null && (
              <WifiIndicator signal={deviceState.wifi_signal} />
            )}
            {!deviceState && (
              <p className="text-xs text-muted-foreground">{camera.stream}</p>
            )}
          </div>
        </div>
        {active && (
          <Button size="sm" variant="ghost" className="text-xs h-7 text-muted-foreground"
            onClick={() => setActive(false)}>
            Stop
          </Button>
        )}
      </div>
    </div>
  )
}
