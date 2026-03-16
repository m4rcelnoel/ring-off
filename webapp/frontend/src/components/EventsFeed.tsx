import { Bell, PersonStanding, Footprints } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { formatRelativeTime } from '@/lib/utils'
import type { Camera, RingEvent } from '@/types'

interface Props {
  events: RingEvent[]
  cameras: Camera[]
}

export default function EventsFeed({ events, cameras }: Props) {
  const cameraName = (id: string) =>
    cameras.find(c => c.id === id || c.stream === id || c.device_id === id)?.name ?? id

  if (!events.length) {
    return (
      <div className="flex flex-col items-center justify-center h-40 text-muted-foreground text-sm gap-2">
        <Bell className="h-8 w-8 opacity-20" />
        <span>No events yet</span>
      </div>
    )
  }

  return (
    <div className="divide-y divide-border">
      {events.map(ev => {
        const isPerson = ev.kind === 'motion' && ev.person_detected
        return (
          <div key={ev.id} className="flex items-center gap-3 px-4 py-3 hover:bg-accent/40 transition-colors animate-fade-in">
            <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
              ev.kind === 'motion'
                ? isPerson
                  ? 'bg-orange-500/10 text-orange-400'
                  : 'bg-amber-500/10 text-amber-400'
                : 'bg-emerald-500/10 text-emerald-400'
            }`}>
              {ev.kind === 'motion'
                ? isPerson
                  ? <PersonStanding className="h-4 w-4" />
                  : <Footprints className="h-4 w-4" />
                : <Bell className="h-4 w-4" />
              }
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{cameraName(ev.device_id)}</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                {ev.kind === 'motion'
                  ? isPerson ? 'Person detected' : 'Motion detected'
                  : 'Doorbell rang'
                } · {formatRelativeTime(ev.timestamp)}
              </p>
            </div>
            <Badge
              variant={ev.kind === 'motion' ? (isPerson ? 'destructive' : 'warning') : 'success'}
              className="shrink-0"
            >
              {isPerson ? 'person' : ev.kind}
            </Badge>
          </div>
        )
      })}
    </div>
  )
}
