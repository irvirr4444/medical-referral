import { useEffect, useRef } from 'react'

type EscapeDismissHandler = () => void

const dismissStack = new Map<symbol, EscapeDismissHandler>()

function dismissTopmost(event: KeyboardEvent) {
  if (event.key !== 'Escape' || event.defaultPrevented) return

  const dismiss = Array.from(dismissStack.values()).at(-1)
  if (!dismiss) return

  event.preventDefault()
  dismiss()
}

export function useEscapeDismiss(
  enabled: boolean,
  onDismiss: EscapeDismissHandler,
) {
  const handlerRef = useRef(onDismiss)
  const registrationRef = useRef(Symbol('escape-dismiss'))

  useEffect(() => {
    handlerRef.current = onDismiss
  }, [onDismiss])

  useEffect(() => {
    if (!enabled) return

    const registration = registrationRef.current
    dismissStack.set(registration, () => handlerRef.current())
    if (dismissStack.size === 1) {
      window.addEventListener('keydown', dismissTopmost)
    }

    return () => {
      dismissStack.delete(registration)
      if (dismissStack.size === 0) {
        window.removeEventListener('keydown', dismissTopmost)
      }
    }
  }, [enabled])
}
