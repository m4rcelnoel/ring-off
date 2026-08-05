import { useEffect, useState } from 'react'

let registration: Promise<boolean> | null = null

// Held in a variable, not inlined: the script is served at runtime by the
// backend's go2rtc proxy and does not exist on disk, so a literal specifier
// would fail Vite's static import analysis at build time.
const VIDEO_RTC_URL = '/proxy/go2rtc/video-rtc.js'

/**
 * Loads go2rtc's video-rtc.js and registers its <video-rtc> custom element.
 *
 * go2rtc ships video-rtc.js as a module that only *exports* the VideoRTC class;
 * the customElements.define() call lives in its separate video-stream.js. Just
 * injecting the script therefore left <video-rtc> permanently unregistered, so
 * every player silently fell back to MJPEG and WebRTC never ran at all.
 */
function registerVideoRtc(): Promise<boolean> {
  if (!registration) {
    registration = import(/* @vite-ignore */ VIDEO_RTC_URL)
      .then((mod: Record<string, unknown>) => {
        const VideoRTC = (mod.VideoRTC ?? mod.default) as CustomElementConstructor | undefined
        if (!VideoRTC) throw new Error('video-rtc.js exported no VideoRTC class')
        if (!customElements.get('video-rtc')) customElements.define('video-rtc', VideoRTC)
        return true
      })
      .catch((err) => {
        console.error('go2rtc video-rtc.js could not be loaded:', err)
        registration = null   // allow a retry on the next mount
        return false
      })
  }
  return registration
}

export function useVideoRtc() {
  const [ready, setReady] = useState(
    () => typeof customElements !== 'undefined' && customElements.get('video-rtc') !== undefined
  )

  useEffect(() => {
    if (ready) return
    let cancelled = false
    registerVideoRtc().then(ok => { if (ok && !cancelled) setReady(true) })
    return () => { cancelled = true }
  }, [ready])

  return ready
}
