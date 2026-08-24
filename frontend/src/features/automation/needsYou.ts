import type { ActionTimer, ConfirmationActionId } from '../../types'

export type NeedsYouVariant = 'choice' | 'schedule'

export interface NeedsYouCopy {
  prompt: (firstName: string) => string
  primary: string
  secondary?: string
  variant: NeedsYouVariant
}

const SHOWCASE_IDS = [
  'frank-owens:eod-escalate',
  'walter-grant:weekly-escalate-dc',
  'thomas-reed:schedule-patient',
  'butler-alva:confirm-partner-contacted',
] as const

const ACTION_COPY: Record<ConfirmationActionId, NeedsYouCopy> = {
  'eod-escalate': {
    prompt: () => "Visit still isn't booked — decide what happens next",
    primary: 'Reschedule',
    secondary: 'Discharge',
    variant: 'choice',
  },
  'weekly-escalate-dc': {
    prompt: () => 'Missed too many visits — decide on discharge',
    primary: 'Discharge',
    secondary: 'Keep active',
    variant: 'choice',
  },
  'schedule-patient': {
    prompt: () => 'Pick a visit time',
    primary: 'Confirm',
    variant: 'schedule',
  },
  'confirm-partner-contacted': {
    prompt: (firstName) => `Did we reach the partner about ${firstName}?`,
    primary: 'Yes, confirm',
    secondary: 'Not yet',
    variant: 'choice',
  },
  'confirm-intake-review': {
    prompt: () => 'Check the extracted information is correct',
    primary: 'Review info',
    variant: 'choice',
  },
  'confirm-assignment': {
    prompt: () => 'Confirm the case manager assignment',
    primary: 'Review manager',
    variant: 'choice',
  },
  'confirm-provider': {
    prompt: () => 'Confirm the suggested provider',
    primary: 'Review provider',
    variant: 'choice',
  },
  'use-fallback-provider': {
    prompt: () => 'No territory match — choose a fallback provider',
    primary: 'Choose provider',
    variant: 'choice',
  },
  'provider-availability': {
    prompt: () => 'Provider still needs to confirm availability',
    primary: 'Check status',
    variant: 'choice',
  },
  'manual-placement': {
    prompt: () => 'Manual placement is waiting on you',
    primary: 'Finish placement',
    variant: 'choice',
  },
  'eod-follow-up-cm': {
    prompt: () => 'Follow up with the case manager on this visit',
    primary: 'Follow up',
    variant: 'choice',
  },
  'weekly-mark-not-seen': {
    prompt: () => 'Visit was missed — mark not seen and reschedule',
    primary: 'Mark not seen',
    variant: 'choice',
  },
  'weekly-confirm-rescheduled': {
    prompt: () => 'Confirm the weekly visit was rescheduled',
    primary: 'Confirm reschedule',
    variant: 'choice',
  },
  'weekly-qa-discharge': {
    prompt: () => 'Wound healed — send for QA discharge review',
    primary: 'Send for review',
    variant: 'choice',
  },
  'weekly-remove-dc': {
    prompt: () => 'Expired — remove from schedule pending discharge',
    primary: 'Remove from schedule',
    variant: 'choice',
  },
  'weekly-move-holds': {
    prompt: () => 'Move this patient to the holds team',
    primary: 'Move to holds',
    variant: 'choice',
  },
}

export function displayPatientName(name: string) {
  if (!name.includes(',')) return name.trim()
  const [family, given] = name.split(',', 2)
  return `${given.trim()} ${family.trim()}`.trim()
}

export function patientFirstName(name: string) {
  const display = displayPatientName(name)
  return display.split(/\s+/)[0] ?? display
}

export function needsYouCopy(actionId: ConfirmationActionId) {
  return ACTION_COPY[actionId]
}

const URGENCY_RANK: Record<ActionTimer['status'], number> = {
  overdue: 0,
  warning: 1,
  pending: 2,
  resolved: 3,
}

/**
 * Every open timer, showcase patients first, then most-urgent first. The
 * component decides how many to show; totals always match this list so the
 * "Showing X of Y" copy never lies.
 */
export function needsYouDigest(timers: Record<string, ActionTimer>) {
  const open = Object.values(timers).filter((timer) => timer.status !== 'resolved')
  const byId = new Map(open.map((timer) => [timer.id, timer]))
  const showcase = SHOWCASE_IDS.map((id) => byId.get(id)).filter(
    (timer): timer is ActionTimer => Boolean(timer),
  )
  const used = new Set(showcase.map((timer) => timer.id))
  const rest = open
    .filter((timer) => !used.has(timer.id))
    .sort(
      (a, b) =>
        URGENCY_RANK[a.status] - URGENCY_RANK[b.status] ||
        a.deadlineAt - b.deadlineAt,
    )

  return {
    ordered: [...showcase, ...rest],
    lateTotal: open.filter((timer) => timer.status === 'overdue').length,
    waitingTotal: open.length,
  }
}
