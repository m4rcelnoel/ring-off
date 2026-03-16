import { useEffect, useState } from 'react'
import { HomeIcon } from 'lucide-react'
import { api } from '@/lib/api'
import type { HAEntity } from '@/types'

export default function HAPanel() {
  const [entities, setEntities] = useState<HAEntity[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.get<HAEntity[]>('/api/ha/entities')
      .then(setEntities)
      .catch(e => setError(e.message))
  }, [])

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-32 gap-2 text-muted-foreground text-sm px-4 text-center">
        <HomeIcon className="h-7 w-7 opacity-20" />
        <span>Configure Home Assistant in settings</span>
      </div>
    )
  }

  if (!entities.length) {
    return (
      <div className="flex flex-col items-center justify-center h-32 gap-2 text-muted-foreground text-sm">
        <HomeIcon className="h-7 w-7 opacity-20" />
        <span>No Ring entities found</span>
      </div>
    )
  }

  return (
    <div className="divide-y divide-border">
      {entities.map(e => {
        const name = e.attributes.friendly_name ?? e.entity_id
        const stateClass =
          e.state === 'on' ? 'text-emerald-400 bg-emerald-500/10' :
          e.state === 'off' ? 'text-muted-foreground bg-muted' :
          'text-primary bg-primary/10'

        return (
          <div key={e.entity_id} className="flex items-center justify-between px-4 py-2.5 hover:bg-accent/40 transition-colors">
            <span className="text-sm truncate max-w-[65%]" title={e.entity_id}>{String(name)}</span>
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${stateClass}`}>
              {e.state}
            </span>
          </div>
        )
      })}
    </div>
  )
}
