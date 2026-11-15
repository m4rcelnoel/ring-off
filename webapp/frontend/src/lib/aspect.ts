import { useSyncExternalStore } from 'react'

/**
 * Per-camera aspect ratio, learned from the pixels the camera actually sends.
 *
 * Ring hardware differs: the Video Doorbell 3 is 16:9, newer "head-to-toe"
 * doorbells are square. A fixed box either squeezes or crops one of them, so
 * the ratio is taken from the snapshot (available before a stream starts) and
 * refined by the live video once it plays. 16:9 until either is known.
 */

export const DEFAULT_ASPECT = 16 / 9

const ratios = new Map<string, number>()
const listeners = new Set<() => void>()

export function reportAspect(key: string | null | undefined, width: number, height: number) {
  if (!key || !width || !height) return
  // Clamp so a corrupt frame cannot produce an absurd layout.
  const ratio = Math.min(2.5, Math.max(0.5, width / height))
  const known = ratios.get(key)
  if (known !== undefined && Math.abs(known - ratio) < 0.01) return
  ratios.set(key, ratio)
  listeners.forEach(notify => notify())
}

function subscribe(notify: () => void) {
  listeners.add(notify)
  return () => { listeners.delete(notify) }
}

export function useAspect(key: string | null | undefined): number {
  return useSyncExternalStore(subscribe, () => (key && ratios.get(key)) || DEFAULT_ASPECT)
}
