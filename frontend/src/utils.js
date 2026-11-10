import { useEffect, useRef, useState } from 'react'

export const fmt = (n) => Math.round(n).toLocaleString('ru-RU')

export function plural(n, one, few, many) {
  const m10 = n % 10, m100 = n % 100
  if (m10 === 1 && m100 !== 11) return one
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return few
  return many
}

export const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches

/* Плавно «набегающее» число: при смене target число доезжает до него за ms миллисекунд. */
export function useCountUp(target, ms = 900, startFrom = 0) {
  const [value, setValue] = useState(startFrom)
  const current = useRef(startFrom)

  useEffect(() => {
    if (reducedMotion() || current.current === target) {
      current.current = target
      setValue(target)
      return undefined
    }
    const from = current.current
    const t0 = performance.now()
    let raf
    const tick = (t) => {
      const k = Math.min(1, (t - t0) / ms)
      current.current = from + (target - from) * (1 - Math.pow(1 - k, 3))
      setValue(current.current)
      if (k < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, ms])

  return value
}

/* true через кадр-другой после монтирования: нужно, чтобы запустить CSS-переходы (шкалы, кольцо). */
export function useAfterMount() {
  const [ready, setReady] = useState(false)
  useEffect(() => {
    const id = requestAnimationFrame(() => requestAnimationFrame(() => setReady(true)))
    return () => cancelAnimationFrame(id)
  }, [])
  return ready
}
