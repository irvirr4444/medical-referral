import { useEffect, useState } from 'react'

interface CountUpProps {
  value: number
  format?: (n: number) => string
  durationMs?: number
}

export function CountUp({ value, format = String, durationMs = 700 }: CountUpProps) {
  const [display, setDisplay] = useState(value)

  useEffect(() => {
    const reduced =
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduced || display === value) {
      setDisplay(value)
      return
    }

    const start = display
    const delta = value - start
    const startedAt = performance.now()
    let frame = 0

    const tick = (now: number) => {
      const progress = Math.min(1, (now - startedAt) / durationMs)
      const eased = 1 - (1 - progress) ** 3
      setDisplay(Math.round(start + delta * eased))
      if (progress < 1) frame = requestAnimationFrame(tick)
    }

    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
    // Intentionally animate from previous displayed value when `value` changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, durationMs])

  return <span>{format(display)}</span>
}
