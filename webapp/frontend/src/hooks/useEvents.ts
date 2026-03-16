import { useEffect, useRef, useState } from 'react'
import type { DeviceStates, RingEvent } from '@/types'

export function useEvents(onNewEvent?: (e: RingEvent) => void) {
  const [events, setEvents] = useState<RingEvent[]>([])
  const [deviceStates, setDeviceStates] = useState<DeviceStates>({})
  const [connected, setConnected] = useState(false)
  const cbRef = useRef(onNewEvent)
  cbRef.current = onNewEvent

  useEffect(() => {
    let ws: WebSocket
    let reconnectTimer: ReturnType<typeof setTimeout>

    function connect() {
      const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
      ws = new WebSocket(`${proto}//${location.host}/ws/events`)

      ws.onopen = () => setConnected(true)
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data)
        if (msg.type === 'history') {
          setEvents(msg.data)
        } else if (msg.type === 'event') {
          setEvents(prev => [msg.data, ...prev].slice(0, 100))
          cbRef.current?.(msg.data)
        } else if (msg.type === 'device_states') {
          setDeviceStates(msg.data)
        } else if (msg.type === 'device_state') {
          setDeviceStates(prev => ({ ...prev, [msg.device_id]: msg.data }))
        }
      }

      const ping = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send('ping')
      }, 30000)

      ws.onclose = () => {
        clearInterval(ping)
        setConnected(false)
        reconnectTimer = setTimeout(connect, 3000)
      }
    }

    connect()
    return () => {
      clearTimeout(reconnectTimer)
      ws?.close()
    }
  }, [])

  return { events, deviceStates, connected }
}
