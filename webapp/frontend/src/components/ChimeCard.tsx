import { Bell, Wifi } from 'lucide-react'
import type { DeviceState } from '@/types'

interface Props {
  deviceState: DeviceState
  name: string
}

function signalColor(signal: number) {
  return signal >= -60 ? 'text-emerald-400' : signal >= -75 ? 'text-amber-400' : 'text-red-400'
}

export default function ChimeCard({ deviceState, name }: Props) {
  return (
    <div className="flex items-center gap-3 px-4 py-3 border-b border-border last:border-0">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10">
        <Bell className="h-4 w-4 text-primary" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{name}</p>
        <div className="flex items-center gap-3 mt-0.5">
          {deviceState.wifi_signal != null && (
            <span className={`flex items-center gap-1 text-[10px] font-medium ${signalColor(deviceState.wifi_signal)}`}
              title={deviceState.wifi_network ?? undefined}>
              <Wifi className="h-3 w-3" />
              {deviceState.wifi_signal} dBm
            </span>
          )}
          {deviceState.wifi_network && (
            <span className="text-[10px] text-muted-foreground truncate">{deviceState.wifi_network}</span>
          )}
        </div>
      </div>
      {deviceState.firmware && (
        <span className="text-[10px] text-muted-foreground shrink-0">{deviceState.firmware}</span>
      )}
    </div>
  )
}
