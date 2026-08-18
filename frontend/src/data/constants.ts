import type {
  BatchMetrics,
  ImpactAssumptions,
  ImpactProjection,
  ReferralRecord,
  WorkflowStage,
} from '../types'
import { WCW_NETWORK } from './wcw'

export const OPERATING_DATE = 'Friday, August 7, 2026'
export const INBOX_ADDRESS = 'info@westcoastwound.com'
export const WAITING_INBOX_COUNT = 7

/** Baseline mid-morning totals already on the board before the next inbox run. */
export const BASELINE_METRICS: BatchMetrics = {
  emailsReceived: 11,
  pdfsProcessed: 11,
  pagesAnalyzed: 148,
  valuesExtracted: 214,
  requiredFieldsEvaluated: 77,
  duplicateSearches: 11,
  mondayPreviewsGenerated: 11,
  drkDraftsGenerated: 11,
  destinationReady: 7,
  incompleteOrUnclear: 2,
  probableDuplicatesBlocked: 1,
  readyForConfirmation: 3,
  manualActionsAvoided: 84,
  timeReturnedMinutes: 252,
}

/** Metrics added when the waiting inbox batch of 7 is processed. */
export const INBOX_BATCH_DELTA: BatchMetrics = {
  emailsReceived: 7,
  pdfsProcessed: 7,
  pagesAnalyzed: 132,
  valuesExtracted: 189,
  requiredFieldsEvaluated: 49,
  duplicateSearches: 7,
  mondayPreviewsGenerated: 7,
  drkDraftsGenerated: 7,
  destinationReady: 4,
  incompleteOrUnclear: 2,
  probableDuplicatesBlocked: 1,
  readyForConfirmation: 4,
  manualActionsAvoided: 63,
  timeReturnedMinutes: 196,
}

export const DEFAULT_IMPACT_ASSUMPTIONS: ImpactAssumptions = {
  referralsPerDay: 18,
  manualMinutes: 36,
  assistedMinutes: 8,
  workingDaysPerYear: 250,
  annualProductiveHours: 2080,
}

export const WORKFLOW_STAGES: Array<{ id: WorkflowStage; label: string }> = [
  { id: 'received', label: 'Received' },
  { id: 'extracted', label: 'Extracted' },
  { id: 'reviewed', label: 'Reviewed' },
  { id: 'confirmed', label: 'Confirmed' },
  { id: 'monday_ready', label: 'Monday.com Ready' },
  { id: 'drk_ready', label: 'DRK Ready' },
]

export const AUTOMATION_STEPS = [
  { id: 'connecting', label: 'Connecting to referral inbox' },
  { id: 'discovering', label: 'Discovering new referral emails' },
  { id: 'validating', label: 'Validating PDF attachments' },
  { id: 'deduping_attachments', label: 'Checking that attachments were not already processed' },
  { id: 'reading', label: 'Reading referral documents' },
  { id: 'verifying', label: 'Verifying extracted information against the source' },
  { id: 'evaluating', label: 'Evaluating the seven required fields' },
  { id: 'duplicate_search', label: 'Searching for possible Monday.com duplicates' },
  { id: 'monday_prep', label: 'Preparing Monday.com records' },
  { id: 'drk_prep', label: 'Preparing DRK charts' },
  { id: 'review_summaries', label: 'Building human-review summaries' },
  { id: 'complete', label: 'Inbox batch complete' },
] as const

export const COMPLETION_MESSAGE =
  'Inbox processed. Four referrals ready for confirmation, two need information, one possible duplicate blocked.'

export function addMetrics(a: BatchMetrics, b: BatchMetrics): BatchMetrics {
  return {
    emailsReceived: a.emailsReceived + b.emailsReceived,
    pdfsProcessed: a.pdfsProcessed + b.pdfsProcessed,
    pagesAnalyzed: a.pagesAnalyzed + b.pagesAnalyzed,
    valuesExtracted: a.valuesExtracted + b.valuesExtracted,
    requiredFieldsEvaluated: a.requiredFieldsEvaluated + b.requiredFieldsEvaluated,
    duplicateSearches: a.duplicateSearches + b.duplicateSearches,
    mondayPreviewsGenerated: a.mondayPreviewsGenerated + b.mondayPreviewsGenerated,
    drkDraftsGenerated: a.drkDraftsGenerated + b.drkDraftsGenerated,
    destinationReady: a.destinationReady + b.destinationReady,
    incompleteOrUnclear: a.incompleteOrUnclear + b.incompleteOrUnclear,
    probableDuplicatesBlocked: a.probableDuplicatesBlocked + b.probableDuplicatesBlocked,
    readyForConfirmation: a.readyForConfirmation + b.readyForConfirmation,
    manualActionsAvoided: a.manualActionsAvoided + b.manualActionsAvoided,
    timeReturnedMinutes: a.timeReturnedMinutes + b.timeReturnedMinutes,
  }
}

export function computeImpact(a: ImpactAssumptions): ImpactProjection {
  const minutesReturnedPerReferral = Math.max(0, a.manualMinutes - a.assistedMinutes)
  const hoursPerDay = (minutesReturnedPerReferral * a.referralsPerDay) / 60
  const hoursPerWeek = hoursPerDay * 5
  const hoursPerYear = (minutesReturnedPerReferral * a.referralsPerDay * a.workingDaysPerYear) / 60
  const addedReferralCapacity =
    a.assistedMinutes > 0
      ? Math.round((a.manualMinutes / a.assistedMinutes - 1) * a.referralsPerDay * a.workingDaysPerYear)
      : 0
  const fteEquivalent = a.annualProductiveHours > 0 ? hoursPerYear / a.annualProductiveHours : 0
  const reductionPercent =
    a.manualMinutes > 0 ? Math.round((minutesReturnedPerReferral / a.manualMinutes) * 100) : 0
  return {
    minutesReturnedPerReferral,
    hoursPerDay,
    hoursPerWeek,
    hoursPerYear,
    addedReferralCapacity,
    fteEquivalent,
    reductionPercent,
  }
}

export function formatMinutes(total: number): string {
  const h = Math.floor(total / 60)
  const m = total % 60
  if (h === 0) return `${m}m`
  if (m === 0) return `${h}h`
  return `${h}h ${m}m`
}

export function stageCounts(referrals: ReferralRecord[]): Record<WorkflowStage | 'all', number> {
  const counts: Record<WorkflowStage | 'all', number> = {
    all: referrals.length,
    received: 0,
    extracted: 0,
    reviewed: 0,
    confirmed: 0,
    monday_ready: 0,
    drk_ready: 0,
  }
  for (const r of referrals) {
    counts[r.stage] += 1
  }
  return counts
}

export const COPY = {
  headline: 'Referral command center for today’s inbox and active cases',
  subhead:
    'Incoming referrals are read, checked, and prepared for Monday.com and DRK so the team reviews exceptions and confirms the next action.',
  liveBadge: `Live · ${INBOX_ADDRESS}`,
  networkLabel: `${WCW_NETWORK.caseManagerCount} case managers · ${WCW_NETWORK.providerCount} providers · ${WCW_NETWORK.facilityCount} DRK facilities`,
  beforeAfterHeadline: '36 minutes of manual intake → 8 minutes of focused review',
  humanControl:
    'Automation prepares information and monitors deadlines. WCW employees retain patient, clinical, scheduling, and approval decisions.',
  confidentialNotice:
    'Source PDF attached to the referral thread. Review against the extracted fields before confirming.',
  capacityCaption: 'Adjust volume and review time to project annual capacity returned to the team.',
  drkReadyLabel: 'DRK chart ready · Create Patient remains human-controlled',
} as const

export const WORKFLOW_TAB_MINUTES: Record<string, number> = {
  intake: 28,
  handoff: 10,
  assignment: 12,
  provider: 14,
  scheduling: 18,
  'end-of-day': 15,
  weekly: 14,
}

export const WORKFLOW_MODAL_TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'intake', label: '1. Referral intake' },
  { id: 'assignment', label: '2. Assignment & handoff' },
  { id: 'provider', label: '3. Provider selection' },
  { id: 'scheduling', label: '4. Scheduling' },
  { id: 'end-of-day', label: '5. End-of-day check' },
  { id: 'weekly', label: '6. Weekly visit cycle' },
] as const
