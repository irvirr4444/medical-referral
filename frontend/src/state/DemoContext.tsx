import {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { AUTOMATION_STEPS } from '../data/constants'
import { createInitialState, demoReducer } from './demoReducer'
import { filterReferrals } from './demoReducer'
import type { AutomationStep } from '../types'
import { DemoContext } from './demoContextValue'

const STEP_MS = 850
const REDUCED_STEP_MS = 120

export function DemoProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(demoReducer, undefined, createInitialState)
  const timers = useRef<number[]>([])
  const prefersReducedMotion = usePrefersReducedMotion()

  const clearTimers = useCallback(() => {
    timers.current.forEach((id) => window.clearTimeout(id))
    timers.current = []
  }, [])

  useEffect(() => () => clearTimers(), [clearTimers])

  const runAutomation = useCallback(() => {
    if (state.automationRunning || state.automationComplete) return
    clearTimers()
    dispatch({ type: 'START_AUTOMATION' })
    const delay = prefersReducedMotion ? REDUCED_STEP_MS : STEP_MS
    AUTOMATION_STEPS.forEach((step, index) => {
      const id = window.setTimeout(() => {
        if (step.id === 'complete') {
          dispatch({ type: 'COMPLETE_AUTOMATION' })
        } else {
          dispatch({ type: 'ADVANCE_AUTOMATION', step: step.id as AutomationStep })
        }
      }, delay * (index + 1))
      timers.current.push(id)
    })
  }, [
    clearTimers,
    prefersReducedMotion,
    state.automationComplete,
    state.automationRunning,
  ])

  const filteredReferrals = useMemo(() => filterReferrals(state), [state])
  const selectedReferral =
    state.referrals.find((referral) => referral.id === state.selectedReferralId) ?? null

  const value = useMemo(
    () => ({
      state,
      dispatch,
      filteredReferrals,
      selectedReferral,
      runAutomation,
      prefersReducedMotion,
    }),
    [state, filteredReferrals, selectedReferral, runAutomation, prefersReducedMotion],
  )

  return <DemoContext.Provider value={value}>{children}</DemoContext.Provider>
}

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false)
  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    setReduced(media.matches)
    const onChange = () => setReduced(media.matches)
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [])
  return reduced
}
