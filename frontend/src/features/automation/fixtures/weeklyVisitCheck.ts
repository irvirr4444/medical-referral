import { caseManagerSuggestion } from './caseManagerAssignments'
import { providerSuggestion } from './providerAssignments'

export type WeeklyVisitOutcome =
  | 'seen'
  | 'not_seen'
  | 'on_hold'
  | 'healed'
  | 'expired'

export interface WeeklyVisitCheckRecord {
  providerName: string
  caseManagerName: string
  visitOutcome: WeeklyVisitOutcome
  visitStatusLabel: string
  lastVisitAt: string
  consecutiveNotSeen: number
  holdReason?: string
  dischargeReviewQueued?: boolean
  movedToHolds?: boolean
  closureActionTaken?: boolean
}

export const WEEKLY_NOT_SEEN_REVIEW_THRESHOLD = 3

const WEEKLY_VISIT_CHECKS: Record<
  string,
  Omit<WeeklyVisitCheckRecord, 'caseManagerName' | 'providerName'>
> = {
  'gloria-bennett': {
    visitOutcome: 'seen',
    visitStatusLabel: 'Seen',
    lastVisitAt: 'August 10, 2026 at 6:01 PM',
    consecutiveNotSeen: 0,
  },
  'dorothy-lane': {
    visitOutcome: 'seen',
    visitStatusLabel: 'Seen',
    lastVisitAt: 'August 9, 2026 at 6:01 PM',
    consecutiveNotSeen: 0,
  },
  'helen-park': {
    visitOutcome: 'seen',
    visitStatusLabel: 'Seen',
    lastVisitAt: 'August 9, 2026 at 6:05 PM',
    consecutiveNotSeen: 0,
  },
  'james-carter': {
    visitOutcome: 'expired',
    visitStatusLabel: 'Expired',
    lastVisitAt: 'August 8, 2026 at 6:03 PM',
    consecutiveNotSeen: 0,
    closureActionTaken: false,
  },
  'maria-alvarez': {
    visitOutcome: 'expired',
    visitStatusLabel: 'Expired',
    lastVisitAt: 'August 10, 2026 at 5:40 PM',
    consecutiveNotSeen: 0,
    closureActionTaken: false,
  },
  'thomas-reed': {
    visitOutcome: 'expired',
    visitStatusLabel: 'Expired',
    lastVisitAt: 'August 9, 2026 at 5:20 PM',
    consecutiveNotSeen: 0,
    closureActionTaken: true,
  },
  'marcus-feldman': {
    visitOutcome: 'expired',
    visitStatusLabel: 'Expired',
    lastVisitAt: 'August 10, 2026 at 4:55 PM',
    consecutiveNotSeen: 0,
    closureActionTaken: true,
  },
  'nancy-liu': {
    visitOutcome: 'healed',
    visitStatusLabel: 'Healed',
    lastVisitAt: 'August 10, 2026 at 6:05 PM',
    consecutiveNotSeen: 0,
  },
  'irene-cho': {
    visitOutcome: 'healed',
    visitStatusLabel: 'Healed',
    lastVisitAt: 'August 10, 2026 at 5:12 PM',
    consecutiveNotSeen: 0,
  },
  'betty-hayes': {
    visitOutcome: 'healed',
    visitStatusLabel: 'Healed',
    lastVisitAt: 'August 9, 2026 at 4:48 PM',
    consecutiveNotSeen: 0,
    closureActionTaken: true,
  },
  'david-ruiz': {
    visitOutcome: 'healed',
    visitStatusLabel: 'Healed',
    lastVisitAt: 'August 10, 2026 at 3:30 PM',
    consecutiveNotSeen: 0,
    closureActionTaken: true,
  },
  'patricia-johnson': {
    visitOutcome: 'not_seen',
    visitStatusLabel: 'Not Seen',
    lastVisitAt: 'August 8, 2026 at 6:01 PM',
    consecutiveNotSeen: 1,
  },
  'margaret-ellis': {
    visitOutcome: 'not_seen',
    visitStatusLabel: 'Not Seen',
    lastVisitAt: 'August 10, 2026 at 6:01 PM',
    consecutiveNotSeen: 2,
  },
  'walter-grant': {
    visitOutcome: 'not_seen',
    visitStatusLabel: 'Not Seen',
    lastVisitAt: 'August 10, 2026 at 6:01 PM',
    consecutiveNotSeen: 3,
  },
  'arthur-kim': {
    visitOutcome: 'on_hold',
    visitStatusLabel: 'On Hold',
    lastVisitAt: 'August 10, 2026 at 6:02 PM',
    consecutiveNotSeen: 0,
    holdReason: 'Hospitalization',
    movedToHolds: false,
  },
  'linda-nguyen': {
    visitOutcome: 'on_hold',
    visitStatusLabel: 'On Hold',
    lastVisitAt: 'August 9, 2026 at 6:07 PM',
    consecutiveNotSeen: 0,
    holdReason: 'Facility hold',
    movedToHolds: true,
  },
  'george-chen': {
    visitOutcome: 'on_hold',
    visitStatusLabel: 'On Hold',
    lastVisitAt: 'August 10, 2026 at 5:05 PM',
    consecutiveNotSeen: 0,
    holdReason: 'Vacation',
    movedToHolds: false,
  },
  'rodriguez-anita': {
    visitOutcome: 'on_hold',
    visitStatusLabel: 'On Hold',
    lastVisitAt: 'August 9, 2026 at 4:20 PM',
    consecutiveNotSeen: 0,
    holdReason: 'Patient request',
    movedToHolds: false,
  },
  'sardina-frank': {
    visitOutcome: 'on_hold',
    visitStatusLabel: 'On Hold',
    lastVisitAt: 'August 8, 2026 at 5:45 PM',
    consecutiveNotSeen: 0,
    holdReason: 'Family request',
    movedToHolds: true,
  },
}

export function weeklyVisitCheckForPatient(
  patientId: string,
): WeeklyVisitCheckRecord {
  const caseManagerName = caseManagerSuggestion(patientId).name
  const providerName = providerSuggestion(patientId).name
  const record = WEEKLY_VISIT_CHECKS[patientId]
  if (record) {
    return { ...record, caseManagerName, providerName }
  }

  return {
    providerName,
    caseManagerName,
    visitOutcome: 'seen',
    visitStatusLabel: 'Seen',
    lastVisitAt: 'Not documented',
    consecutiveNotSeen: 0,
  }
}

export function weeklyVisitCheckSummary(
  record: WeeklyVisitCheckRecord,
): string {
  if (record.visitOutcome === 'seen') {
    return 'Patient seen'
  }
  if (record.visitOutcome === 'not_seen') {
    return `Not seen · ${record.consecutiveNotSeen} consecutive week${
      record.consecutiveNotSeen === 1 ? '' : 's'
    }`
  }
  if (record.visitOutcome === 'on_hold') {
    return `On hold · ${record.holdReason ?? 'monitoring paused'}`
  }
  if (record.visitOutcome === 'healed') {
    return 'Wound healed'
  }
  return 'Patient expired'
}

export function weeklyPatientSeenEligible(
  record: WeeklyVisitCheckRecord,
): boolean {
  return record.visitOutcome === 'seen' || record.visitOutcome === 'not_seen'
}

export function weeklyWoundHealedEligible(
  record: WeeklyVisitCheckRecord,
): boolean {
  return record.visitOutcome === 'healed'
}

export function weeklyPatientExpiredEligible(
  record: WeeklyVisitCheckRecord,
): boolean {
  return record.visitOutcome === 'expired'
}

export function weeklyPatientOnHoldEligible(
  record: WeeklyVisitCheckRecord,
): boolean {
  return record.visitOutcome === 'on_hold'
}

export function weeklyDischargeReviewDue(
  record: WeeklyVisitCheckRecord,
): boolean {
  return (
    record.visitOutcome === 'not_seen' &&
    record.consecutiveNotSeen >= WEEKLY_NOT_SEEN_REVIEW_THRESHOLD
  )
}

export function weeklyMissedVisitPending(
  record: WeeklyVisitCheckRecord,
): boolean {
  return (
    record.visitOutcome === 'not_seen' &&
    record.consecutiveNotSeen > 0 &&
    record.consecutiveNotSeen < WEEKLY_NOT_SEEN_REVIEW_THRESHOLD
  )
}

export function weeklyMissedVisitSummary(
  record: WeeklyVisitCheckRecord,
  options?: {
    dischargeReviewSent?: boolean
    appointmentRescheduled?: boolean
  },
): string {
  if (options?.dischargeReviewSent || record.dischargeReviewQueued) {
    return 'Queued for DC · noncompliance'
  }
  if (options?.appointmentRescheduled) {
    return 'Rescheduled confirmed'
  }
  return 'Marked NOT seen · reschedule weekly'
}

export function weeklyMissedVisitMessage(
  record: WeeklyVisitCheckRecord,
  _patientName: string,
): string {
  if (weeklyDischargeReviewDue(record)) {
    return `Still not seen after ${record.consecutiveNotSeen} consecutive weeks. Sending for upper-management discharge review (noncompliance).`
  }
  return `Not seen this week (${record.consecutiveNotSeen} consecutive). Marked NOT seen and weekly reschedule requested.`
}

export function weeklyHoldsActionComplete(
  record: WeeklyVisitCheckRecord,
  actionTaken = false,
): boolean {
  return (
    actionTaken ||
    Boolean(record.movedToHolds || record.closureActionTaken)
  )
}

export function weeklyHoldsClosuresSummary(
  record: WeeklyVisitCheckRecord,
  actionTaken = false,
): string {
  const done = weeklyHoldsActionComplete(record, actionTaken)
  if (record.visitOutcome === 'on_hold') {
    return done
      ? `Moved to holds team · ${record.holdReason ?? 'on hold'}`
      : `On hold · ${record.holdReason ?? 'monitoring paused'}`
  }
  if (record.visitOutcome === 'healed') {
    return done ? 'Healed · QA discharge path' : 'Wound healed'
  }
  return done ? 'Expired · pending DC approval' : 'Patient expired'
}

export function weeklyHoldsClosuresMessage(
  record: WeeklyVisitCheckRecord,
  patientName: string,
): string {
  if (record.visitOutcome === 'on_hold') {
    return `${patientName} is on hold (${record.holdReason ?? 'other'}). Moved to the holds team and holds list. Weekly visit monitoring pauses until the patient is ready to return.`
  }
  if (record.visitOutcome === 'healed') {
    return `${patientName} wound healed. Provider → QA → discharge path opened. Human approval remains required.`
  }
  return `${patientName} expired. Case manager ${record.caseManagerName} is removing the patient from schedule pending discharge approval.`
}

export function weeklyHoldsClosuresActionLabel(
  record: WeeklyVisitCheckRecord,
): string {
  if (record.visitOutcome === 'on_hold') return 'Move to holds team'
  if (record.visitOutcome === 'healed') return 'Send to QA discharge'
  return 'Remove from schedule · DC'
}

export function weeklyOutcomePanelLabel(
  record: WeeklyVisitCheckRecord,
): string {
  if (record.visitOutcome === 'on_hold') return 'Hold review'
  if (record.visitOutcome === 'healed') return 'Healed discharge review'
  return 'Expired discharge review'
}
