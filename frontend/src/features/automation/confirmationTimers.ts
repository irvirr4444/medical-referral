import type { FlowOpsPageId } from '../../data/flowOps'
import type { ActionTimer, ActionTimerStatus, ConfirmationActionId } from '../../types'

/** Real-world SLA milliseconds. Demo clock divides by DEMO_TIMER_SCALE. */
export const DEMO_TIMER_SCALE = 60
export const WARNING_RATIO = 0.75

export const ACTION_DEFS: Record<
  ConfirmationActionId,
  { stageId: FlowOpsPageId; stepId: string; slaMs: number; label: string }
> = {
  'confirm-intake-review': {
    stageId: 'intake',
    stepId: 'extract-and-verify',
    slaMs: 15 * 60_000,
    label: 'Confirm all information is correct',
  },
  'confirm-partner-contacted': {
    stageId: 'intake',
    stepId: 'confirm-referral-contacted',
    slaMs: 60 * 60_000,
    label: 'Confirm partner is contacted',
  },
  'confirm-assignment': {
    stageId: 'assignment',
    stepId: 'assign-owner',
    slaMs: 30 * 60_000,
    label: 'Confirm case manager',
  },
  'confirm-provider': {
    stageId: 'provider',
    stepId: 'select-provider',
    slaMs: 30 * 60_000,
    label: 'Confirm provider',
  },
  'use-fallback-provider': {
    stageId: 'provider',
    stepId: 'select-provider',
    slaMs: 30 * 60_000,
    label: 'Use selected provider',
  },
  'provider-availability': {
    stageId: 'provider',
    stepId: 'confirm-provider-availability',
    slaMs: 60 * 60_000,
    label: 'Provider confirmed',
  },
  'manual-placement': {
    stageId: 'provider',
    stepId: 'confirm-provider-availability',
    slaMs: 30 * 60_000,
    label: 'Placement completed',
  },
  'schedule-patient': {
    stageId: 'scheduling',
    stepId: 'schedule-patient',
    slaMs: 48 * 60 * 60_000,
    label: 'Schedule patient',
  },
  'eod-follow-up-cm': {
    stageId: 'end-of-day',
    stepId: 'check-scheduling-status',
    slaMs: 24 * 60 * 60_000,
    label: 'Follow up with case manager',
  },
  'eod-escalate': {
    stageId: 'end-of-day',
    stepId: 'check-scheduling-status',
    slaMs: 48 * 60 * 60_000,
    label: 'Escalate unresolved case',
  },
  'weekly-mark-not-seen': {
    stageId: 'weekly',
    stepId: 'patient-seen',
    slaMs: 4 * 60 * 60_000,
    label: 'Mark NOT seen · reschedule',
  },
  'weekly-escalate-dc': {
    stageId: 'weekly',
    stepId: 'patient-seen',
    slaMs: 4 * 60 * 60_000,
    label: 'Escalate for DC (noncompliance)',
  },
  'weekly-confirm-rescheduled': {
    stageId: 'weekly',
    stepId: 'patient-seen',
    slaMs: 4 * 60 * 60_000,
    label: 'Confirm rescheduled',
  },
  'weekly-qa-discharge': {
    stageId: 'weekly',
    stepId: 'wound-healed',
    slaMs: 4 * 60 * 60_000,
    label: 'Send to QA discharge',
  },
  'weekly-remove-dc': {
    stageId: 'weekly',
    stepId: 'patient-expired',
    slaMs: 4 * 60 * 60_000,
    label: 'Remove from schedule · DC',
  },
  'weekly-move-holds': {
    stageId: 'weekly',
    stepId: 'patient-on-hold',
    slaMs: 4 * 60 * 60_000,
    label: 'Move to holds team',
  },
}

export function timerId(patientId: string, actionId: ConfirmationActionId) {
  return `${patientId}:${actionId}`
}

export function deadlineFor(actionId: ConfirmationActionId, eligibleAt: number) {
  return eligibleAt + ACTION_DEFS[actionId].slaMs / DEMO_TIMER_SCALE
}

export function timerStatus(now: number, timer: Pick<ActionTimer, 'eligibleAt' | 'deadlineAt' | 'status'>): ActionTimerStatus {
  if (timer.status === 'resolved') return 'resolved'
  if (now >= timer.deadlineAt) return 'overdue'
  const span = timer.deadlineAt - timer.eligibleAt
  if (span > 0 && (now - timer.eligibleAt) / span >= WARNING_RATIO) return 'warning'
  return 'pending'
}

export function startActionTimer(
  timers: Record<string, ActionTimer>,
  input: {
    patientId: string
    patientName: string
    actionId: ConfirmationActionId
    now: number
  },
): Record<string, ActionTimer> {
  const id = timerId(input.patientId, input.actionId)
  const existing = timers[id]
  if (existing && existing.status !== 'resolved') return timers
  const def = ACTION_DEFS[input.actionId]
  return {
    ...timers,
    [id]: {
      id,
      patientId: input.patientId,
      patientName: input.patientName,
      stageId: def.stageId,
      stepId: def.stepId,
      actionId: input.actionId,
      eligibleAt: input.now,
      deadlineAt: deadlineFor(input.actionId, input.now),
      status: 'pending',
    },
  }
}

export function resolveActionTimer(
  timers: Record<string, ActionTimer>,
  patientId: string,
  actionId: ConfirmationActionId,
  now: number,
): Record<string, ActionTimer> {
  const id = timerId(patientId, actionId)
  const existing = timers[id]
  if (!existing || existing.status === 'resolved') return timers
  return {
    ...timers,
    [id]: { ...existing, status: 'resolved', resolvedAt: now },
  }
}

export function tickActionTimers(
  timers: Record<string, ActionTimer>,
  now: number,
): Record<string, ActionTimer> | null {
  let changed = false
  const next: Record<string, ActionTimer> = { ...timers }
  for (const [id, timer] of Object.entries(timers)) {
    const status = timerStatus(now, timer)
    if (status !== timer.status) {
      next[id] = { ...timer, status }
      changed = true
    }
  }
  return changed ? next : null
}

export function overdueTimers(timers: Record<string, ActionTimer>) {
  return Object.values(timers)
    .filter((timer) => timer.status === 'overdue')
    .sort((a, b) => a.deadlineAt - b.deadlineAt)
}

export function warningTimers(timers: Record<string, ActionTimer>) {
  return Object.values(timers)
    .filter((timer) => timer.status === 'warning')
    .sort((a, b) => a.deadlineAt - b.deadlineAt)
}

export function overdueStageIds(
  timers: Record<string, ActionTimer>,
): Set<string> {
  return new Set(overdueTimers(timers).map((timer) => timer.stageId))
}

export function warningStageIds(
  timers: Record<string, ActionTimer>,
): Set<string> {
  return new Set(warningTimers(timers).map((timer) => timer.stageId))
}

export function overdueStepIds(
  timers: Record<string, ActionTimer>,
  stageId: string,
) {
  return [
    ...new Set(
      overdueTimers(timers)
        .filter((timer) => timer.stageId === stageId)
        .map((timer) => timer.stepId),
    ),
  ]
}

export function warningStepIds(
  timers: Record<string, ActionTimer>,
  stageId: string,
) {
  return [
    ...new Set(
      warningTimers(timers)
        .filter((timer) => timer.stageId === stageId)
        .map((timer) => timer.stepId),
    ),
  ]
}

/** Higher wins. Overdue always outranks a merely unread event. */
export const ATTENTION_RANK: Record<ActionTimerStatus | 'none', number> = {
  overdue: 4,
  warning: 3,
  pending: 2,
  resolved: 1,
  none: 0,
}

export function attentionRank(timer?: ActionTimer | null) {
  return ATTENTION_RANK[timer?.status ?? 'none']
}

/** Sort comparator: most urgent first, oldest deadline breaking ties. */
export function compareAttention(
  a?: ActionTimer | null,
  b?: ActionTimer | null,
) {
  const rankDelta = attentionRank(b) - attentionRank(a)
  if (rankDelta !== 0) return rankDelta
  if (a && b) return a.deadlineAt - b.deadlineAt
  return 0
}

export interface AttentionSummary {
  overdue: ActionTimer[]
  warning: ActionTimer[]
  oldest: ActionTimer | null
  total: number
}

export function attentionSummary(
  timers: Record<string, ActionTimer>,
): AttentionSummary {
  const overdue = overdueTimers(timers)
  const warning = warningTimers(timers)
  return {
    overdue,
    warning,
    oldest: overdue[0] ?? null,
    total: overdue.length,
  }
}

export function timerForPatientStep(
  timers: Record<string, ActionTimer>,
  patientId: string,
  stepId: string,
) {
  return Object.values(timers).find(
    (timer) =>
      timer.patientId === patientId &&
      timer.stepId === stepId &&
      timer.status !== 'resolved',
  )
}

export function actionLabel(actionId: ConfirmationActionId) {
  return ACTION_DEFS[actionId].label
}

/** Live demo clock: seconds tick as seconds (deadlines are already scale-compressed). */
export function formatRemaining(deadlineAt: number, now: number) {
  return formatClockDuration(Math.max(0, deadlineAt - now))
}

export function formatOverdue(deadlineAt: number, now: number) {
  return formatClockDuration(Math.max(0, now - deadlineAt))
}

function formatClockDuration(ms: number) {
  const totalSec = Math.ceil(ms / 1000)
  const hours = Math.floor(totalSec / 3600)
  const minutes = Math.floor((totalSec % 3600) / 60)
  const seconds = totalSec % 60
  if (hours > 0) return `${hours}h ${minutes}m ${String(seconds).padStart(2, '0')}s`
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}

/**
 * Static SLA window in real business time (does not tick — only labels the policy).
 * Live countdowns use formatRemaining / formatOverdue on the compressed demo clock.
 */
export function formatBusinessDuration(ms: number) {
  const totalMinutes = Math.round(Math.max(0, ms) / 60_000)
  if (totalMinutes >= 60) {
    const hours = Math.floor(totalMinutes / 60)
    const minutes = totalMinutes % 60
    return minutes ? `${hours}h ${minutes}m` : `${hours}h`
  }
  if (totalMinutes >= 1) return `${totalMinutes}m`
  return 'under 1m'
}

export function remainingLabel(timer: ActionTimer, now: number) {
  return formatRemaining(timer.deadlineAt, now)
}

export function overdueLabel(timer: ActionTimer, now: number) {
  return formatOverdue(timer.deadlineAt, now)
}

export function slaLabel(actionId: ConfirmationActionId) {
  return formatBusinessDuration(ACTION_DEFS[actionId].slaMs)
}

type SeedState = 'pending' | 'warning' | 'overdue'

interface TimerSeed {
  patientId: string
  patientName: string
  actionId: ConfirmationActionId
  state: SeedState
  /** Demo minutes past the deadline, for overdue seeds. */
  overdueByMinutes?: number
}

/**
 * One scenario per patient per stage, so every confirmation CTA has a cold-start
 * timer without waiting for the demo clock. `weekly-confirm-rescheduled` is
 * intentionally absent: it only becomes eligible after "Mark NOT seen".
 */
export const FLOW_ONLY_ACTION_IDS: ConfirmationActionId[] = [
  'weekly-confirm-rescheduled',
]

export const DEMO_TIMER_SEEDS: TimerSeed[] = [
  // Intake · extract and verify (threshold failures still owe a review)
  { patientId: 'gonzalez-eric', patientName: 'Gonzalez, Eric', actionId: 'confirm-intake-review', state: 'overdue', overdueByMinutes: 22 },
  { patientId: 'sardina-frank', patientName: 'Sardina, Frank', actionId: 'confirm-intake-review', state: 'warning' },

  // Intake · referral partner contacted
  { patientId: 'butler-alva', patientName: 'Butler, Alva', actionId: 'confirm-partner-contacted', state: 'overdue', overdueByMinutes: 74 },
  { patientId: 'eliut-cruz-pagan', patientName: 'Cruz Pagan, Eliut', actionId: 'confirm-partner-contacted', state: 'warning' },
  { patientId: 'rodriguez-anita', patientName: 'Rodriguez, Anita', actionId: 'confirm-partner-contacted', state: 'pending' },

  // Assignment · assign case manager
  { patientId: 'marcus-feldman', patientName: 'Marcus Feldman', actionId: 'confirm-assignment', state: 'overdue', overdueByMinutes: 41 },
  { patientId: 'david-ruiz', patientName: 'David Ruiz', actionId: 'confirm-assignment', state: 'warning' },

  // Provider · select provider
  { patientId: 'maria-alvarez', patientName: 'Maria Alvarez', actionId: 'confirm-provider', state: 'overdue', overdueByMinutes: 18 },
  { patientId: 'betty-hayes', patientName: 'Betty Hayes', actionId: 'use-fallback-provider', state: 'warning' },

  // Provider · availability and manual placement
  { patientId: 'helen-park', patientName: 'Helen Park', actionId: 'provider-availability', state: 'pending' },
  { patientId: 'irene-cho', patientName: 'Irene Cho', actionId: 'manual-placement', state: 'overdue', overdueByMinutes: 35 },

  // Scheduling · appointment placement
  { patientId: 'maria-alvarez', patientName: 'Maria Alvarez', actionId: 'schedule-patient', state: 'overdue', overdueByMinutes: 48 },
  { patientId: 'thomas-reed', patientName: 'Thomas Reed', actionId: 'schedule-patient', state: 'warning' },
  { patientId: 'james-carter', patientName: 'James Carter', actionId: 'schedule-patient', state: 'pending' },

  // End-of-day
  { patientId: 'thomas-reed', patientName: 'Thomas Reed', actionId: 'eod-follow-up-cm', state: 'pending' },
  { patientId: 'frank-owens', patientName: 'Frank Owens', actionId: 'eod-escalate', state: 'overdue', overdueByMinutes: 185 },

  // Weekly visit cycle
  { patientId: 'patricia-johnson', patientName: 'Patricia Johnson', actionId: 'weekly-mark-not-seen', state: 'pending' },
  { patientId: 'margaret-ellis', patientName: 'Margaret Ellis', actionId: 'weekly-mark-not-seen', state: 'warning' },
  { patientId: 'walter-grant', patientName: 'Walter Grant', actionId: 'weekly-escalate-dc', state: 'overdue', overdueByMinutes: 128 },
  { patientId: 'nancy-liu', patientName: 'Nancy Liu', actionId: 'weekly-qa-discharge', state: 'overdue', overdueByMinutes: 52 },
  { patientId: 'james-carter', patientName: 'James Carter', actionId: 'weekly-remove-dc', state: 'overdue', overdueByMinutes: 96 },
  { patientId: 'arthur-kim', patientName: 'Arthur Kim', actionId: 'weekly-move-holds', state: 'overdue', overdueByMinutes: 63 },
  { patientId: 'george-chen', patientName: 'George Chen', actionId: 'weekly-move-holds', state: 'pending' },
]

function buildSeed(now: number, seed: TimerSeed): ActionTimer {
  const def = ACTION_DEFS[seed.actionId]
  const span = def.slaMs / DEMO_TIMER_SCALE

  let eligibleAt: number
  let deadlineAt: number
  if (seed.state === 'overdue') {
    deadlineAt = now - (seed.overdueByMinutes ?? 30) * 60_000 / DEMO_TIMER_SCALE
    eligibleAt = deadlineAt - span
  } else if (seed.state === 'warning') {
    // Just past the 75% warning gate with a little runway left.
    eligibleAt = now - span * 0.85
    deadlineAt = eligibleAt + span
  } else {
    eligibleAt = now - span * 0.2
    deadlineAt = eligibleAt + span
  }

  return {
    id: timerId(seed.patientId, seed.actionId),
    patientId: seed.patientId,
    patientName: seed.patientName,
    stageId: def.stageId,
    stepId: def.stepId,
    actionId: seed.actionId,
    eligibleAt,
    deadlineAt,
    status: seed.state,
  }
}

export function seedActionTimers(now = Date.now()): Record<string, ActionTimer> {
  return Object.fromEntries(
    DEMO_TIMER_SEEDS.map((seed) => {
      const timer = buildSeed(now, seed)
      return [timer.id, timer]
    }),
  )
}

export function timerPatientName(
  timers: Record<string, ActionTimer>,
  patientId: string,
  fallback: string,
) {
  return (
    Object.values(timers).find((timer) => timer.patientId === patientId)
      ?.patientName ?? fallback
  )
}
