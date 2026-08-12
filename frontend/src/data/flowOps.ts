import type { LifecycleStageId } from '../data/lifecycle'

export type FlowOpsPageId =
  | 'intake'
  | 'handoff'
  | 'assignment'
  | 'provider'
  | 'scheduling'
  | 'end-of-day'
  | 'weekly'

export interface FlowOpsConfig {
  id: FlowOpsPageId
  title: string
  blurb: string
  comparisonId: string
  showNetwork: boolean
  showImpact: boolean
  showSpine: boolean
  showQueue: boolean
  showActivity: boolean
  showCapacity: boolean
  lifecycleStages: LifecycleStageId[]
  lifecycleTitle: string
  lifecycleBlurb: string
}

export const FLOW_OPS: Record<FlowOpsPageId, FlowOpsConfig> = {
  intake: {
    id: 'intake',
    title: '1. Referral intake',
    blurb: 'Live inbox processing — extract, verify, and prepare Monday.com / DRK for confirmation.',
    comparisonId: 'intake',
    showNetwork: false,
    showImpact: true,
    showSpine: true,
    showQueue: true,
    showActivity: true,
    showCapacity: false,
    lifecycleStages: [],
    lifecycleTitle: '',
    lifecycleBlurb: '',
  },
  handoff: {
    id: 'handoff',
    title: '3. Handoff',
    blurb: 'Notify the referral source and assigned case manager, then create Monday.com / DRK records.',
    comparisonId: 'handoff',
    showNetwork: false,
    showImpact: false,
    showSpine: false,
    showQueue: false,
    showActivity: true,
    showCapacity: false,
    lifecycleStages: [],
    lifecycleTitle: '',
    lifecycleBlurb: '',
  },
  assignment: {
    id: 'assignment',
    title: '2. Assignment',
    blurb: 'Match patient location to territory rules and confirm the case manager before handoff.',
    comparisonId: 'assignment',
    showNetwork: false,
    showImpact: false,
    showSpine: false,
    showQueue: false,
    showActivity: true,
    showCapacity: false,
    lifecycleStages: [],
    lifecycleTitle: '',
    lifecycleBlurb: '',
  },
  provider: {
    id: 'provider',
    title: '4. Provider selection',
    blurb: 'Suggest company providers by territory and keep send status human-controlled.',
    comparisonId: 'provider',
    showNetwork: false,
    showImpact: false,
    showSpine: false,
    showQueue: false,
    showActivity: true,
    showCapacity: false,
    lifecycleStages: [],
    lifecycleTitle: '',
    lifecycleBlurb: '',
  },
  scheduling: {
    id: 'scheduling',
    title: '5. Scheduling',
    blurb: 'Present route-aware windows and monitor the one-hour provider-response timer.',
    comparisonId: 'scheduling',
    showNetwork: false,
    showImpact: false,
    showSpine: false,
    showQueue: false,
    showActivity: true,
    showCapacity: false,
    lifecycleStages: [],
    lifecycleTitle: '',
    lifecycleBlurb: '',
  },
  'end-of-day': {
    id: 'end-of-day',
    title: '6. End-of-day check',
    blurb: 'Scan unscheduled referrals after the deadline and build one management exception list.',
    comparisonId: 'end-of-day',
    showNetwork: false,
    showImpact: false,
    showSpine: false,
    showQueue: false,
    showActivity: true,
    showCapacity: false,
    lifecycleStages: [],
    lifecycleTitle: '',
    lifecycleBlurb: '',
  },
  weekly: {
    id: 'weekly',
    title: '7. Weekly visit cycle',
    blurb: 'Track seen / not-seen visits, holds, healed/expired statuses, and discharge approvals.',
    comparisonId: 'weekly',
    showNetwork: false,
    showImpact: false,
    showSpine: false,
    showQueue: false,
    showActivity: true,
    showCapacity: false,
    lifecycleStages: [],
    lifecycleTitle: '',
    lifecycleBlurb: '',
  },
}

export function isFlowOpsPage(page: string): page is FlowOpsPageId {
  return page in FLOW_OPS
}
