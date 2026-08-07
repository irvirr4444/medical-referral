import { createContext, type Dispatch } from 'react'
import type { DemoAction } from './demoReducer'
import type { DemoState, ReferralRecord } from '../types'

export interface DemoContextValue {
  state: DemoState
  dispatch: Dispatch<DemoAction>
  filteredReferrals: ReferralRecord[]
  selectedReferral: ReferralRecord | null
  runAutomation: () => void
  prefersReducedMotion: boolean
}

export const DemoContext = createContext<DemoContextValue | null>(null)
