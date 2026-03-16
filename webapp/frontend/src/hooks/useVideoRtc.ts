import { useEffect, useState } from 'react'

let injected = false

/** Injects go2rtc's video-rtc.js as a module script and waits for the custom element. */
export function useVideoRtc() {
  const [ready, setReady] = useState(
    () => typeof customElements !== 'undefined' && customElements.get('video-rtc') !== undefined
  )

  useEffect(() => {
    if (ready) return

    if (!injected) {
      injected = true
      const script = document.createElement('script')
      script.type = 'module'
      script.src = '/proxy/go2rtc/video-rtc.js'
      document.head.appendChild(script)
    }

    // Poll until the custom element is registered
    const interval = setInterval(() => {
      if (customElements.get('video-rtc')) {
        setReady(true)
        clearInterval(interval)
      }
    }, 150)

    return () => clearInterval(interval)
  }, [ready])

  return ready
}
