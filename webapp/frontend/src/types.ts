export interface Camera {
  id: string
  name: string
  stream: string
  device_id?: string | null
  has_snapshot?: boolean
}

export interface DeviceState {
  id: string
  type: 'camera' | 'chime'
  location_id: string
  battery_level?: number | null
  firmware?: string | null
  last_update?: string | null
  wifi_network?: string | null
  wifi_signal?: number | null
}

export type DeviceStates = Record<string, DeviceState>

export interface RingEvent {
  id: string
  device_id: string
  location_id: string
  kind: 'motion' | 'ding'
  timestamp: string
  person_detected?: boolean
}

export interface Clip {
  device_id: string
  filename: string
  path: string
  size: number
  created: string
  kind: 'motion' | 'ding'
}

export interface HAEntity {
  entity_id: string
  state: string
  attributes: { friendly_name?: string; [key: string]: unknown }
}

export interface Settings {
  ha_url: string
  ha_token_set: boolean
  record_motion: boolean
  record_ding: boolean
  record_duration: number
  retention_days: number
  notify_url: string
  notify_on_motion: boolean
  notify_on_ding: boolean
  app_password_set: boolean
}

export interface Status {
  ring_configured: boolean
  ha_configured: boolean
}

export interface AppStatus {
  auth_required: boolean
  authenticated: boolean
}
