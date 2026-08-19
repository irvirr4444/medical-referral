import type { FlowOpsPageId } from '../../../data/flowOps'
import type { ActionTimer, ActionTimerStatus, AttentionSeverity } from '../../../types'
import type { DemoAction } from '../../../state/demoReducer'
import type { AttentionSignal } from './attention'

const STAGE_PAGES: Record<number, FlowOpsPageId> = {
  1: 'intake',
  2: 'assignment',
  3: 'assignment',
  4: 'provider',
  5: 'scheduling',
  6: 'end-of-day',
  7: 'weekly',
}

export function selectAttentionTimers(input: {
  liveStatus: 'loading' | 'connected' | 'unavailable'
  liveItems: AttentionSignal[]
  demoMode: boolean
  demoTimers: Record<string, ActionTimer>
}): Record<string, ActionTimer> {
  if (input.liveStatus === 'connected') {
    return timersFromSignals(input.liveItems)
  }
  if (input.demoMode) return input.demoTimers
  return {}
}

export function timersFromSignals(items: AttentionSignal[]): Record<string, ActionTimer> {
  return Object.fromEntries(
    items.map((item) => {
      const timer = timerFromSignal(item)
      return [timer.id, timer]
    }),
  )
}

export function timerFromSignal(item: AttentionSignal): ActionTimer {
  return {
    id: item.signal_id,
    patientId: item.case_id,
    patientName: item.patient_label || 'Patient',
    stageId: stagePageId(item.stage),
    stepId: item.step_id,
    actionId: 'confirm-intake-review',
    label: item.action_label,
    eligibleAt: 0,
    deadlineAt: item.due_at ? Date.parse(item.due_at) : 0,
    status: severityToTimerStatus(item.severity),
    attentionSeverity: item.severity,
  }
}

export function applyAttentionNavigation(
  timer: ActionTimer,
  dispatch: (action: DemoAction) => void,
) {
  dispatch({ type: 'SET_ACTIVE_PAGE', page: timer.stageId })
  dispatch({ type: 'SET_OPS_SELECTED_STEP', stageId: timer.stageId, stepId: timer.stepId })
  dispatch({
    type: 'SCOPE_OPS_PATIENT',
    patientId: timer.patientId,
    patientName: timer.patientName,
  })
}

export function stagePageId(stage: number): FlowOpsPageId {
  return STAGE_PAGES[stage] ?? 'intake'
}

export function severityToTimerStatus(severity: AttentionSignal['severity']): ActionTimerStatus {
  if (severity === 'overdue' || severity === 'blocked') return 'overdue'
  if (severity === 'due_soon') return 'warning'
  return 'pending'
}

/** Live signals keep their severity. Legacy demo timers fall back to status, never to blocked. */
export function timerAttentionSeverity(timer: ActionTimer): AttentionSeverity | null {
  if (timer.status === 'resolved') return null
  if (timer.attentionSeverity) return timer.attentionSeverity
  if (timer.status === 'overdue') return 'overdue'
  if (timer.status === 'warning') return 'due_soon'
  if (timer.status === 'pending') return 'normal'
  return null
}

function byOldest(a: ActionTimer, b: ActionTimer) {
  if (a.deadlineAt !== b.deadlineAt) return a.deadlineAt - b.deadlineAt
  return a.id.localeCompare(b.id)
}

export function attentionGroups(timers: Iterable<ActionTimer>) {
  const blocked: ActionTimer[] = []
  const overdue: ActionTimer[] = []
  const dueSoon: ActionTimer[] = []
  for (const timer of timers) {
    const severity = timerAttentionSeverity(timer)
    if (severity === 'blocked') blocked.push(timer)
    else if (severity === 'overdue') overdue.push(timer)
    else if (severity === 'due_soon') dueSoon.push(timer)
  }
  blocked.sort(byOldest)
  overdue.sort(byOldest)
  dueSoon.sort(byOldest)
  return { blocked, overdue, dueSoon }
}

export function attentionAriaSuffix(timer?: ActionTimer | null) {
  const severity = timer ? timerAttentionSeverity(timer) : null
  if (severity === 'blocked') return ' · Needs attention · blocked'
  if (severity === 'overdue') return ' · Immediate attention · overdue'
  if (severity === 'due_soon') return ' · Due soon'
  return ''
}

export function countsByStep(
  timers: Iterable<ActionTimer>,
  stageId: string,
  severity: AttentionSeverity,
): Record<string, number> {
  const counts: Record<string, number> = {}
  for (const timer of timers) {
    if (timer.stageId !== stageId || timerAttentionSeverity(timer) !== severity) continue
    counts[timer.stepId] = (counts[timer.stepId] ?? 0) + 1
  }
  return counts
}

export function stepIdsWithSeverity(
  timers: Iterable<ActionTimer>,
  stageId: string,
  severity: AttentionSeverity,
) {
  return [
    ...new Set(
      [...timers]
        .filter(
          (timer) =>
            timer.stageId === stageId && timerAttentionSeverity(timer) === severity,
        )
        .map((timer) => timer.stepId),
    ),
  ]
}

export type AttentionBannerModel = {
  headline: string
  badge: string
  meta: string
  target: ActionTimer
  ariaLabel: string
}

export function attentionBannerModel(
  timers: Iterable<ActionTimer>,
  options?: { scopeSuffix?: string; stageScoped?: boolean },
): AttentionBannerModel | null {
  const { blocked, overdue, dueSoon } = attentionGroups(timers)
  const target = blocked[0] ?? overdue[0] ?? dueSoon[0]
  if (!target) return null

  const scope = options?.scopeSuffix ?? ''
  const overdueMeta = overdue.length ? `${overdue.length} overdue` : ''
  const dueSoonMeta = dueSoon.length ? `${dueSoon.length} due soon` : ''

  if (blocked.length) {
    const headline =
      blocked.length === 1
        ? `1 workflow issue needs attention${scope}`
        : `${blocked.length} workflow issues need attention${scope}`
    return {
      headline,
      badge: 'Blocked',
      meta: [overdueMeta, dueSoonMeta].filter(Boolean).join(' · '),
      target,
      ariaLabel: `${headline}. Oldest is ${target.label ?? target.actionId} for ${target.patientName}.`,
    }
  }

  if (overdue.length) {
    const headline =
      overdue.length === 1
        ? `1 action is overdue${scope}`
        : `${overdue.length} actions are overdue${scope}`
    const stages = [...new Set(overdue.map((timer) => timer.stageId))]
    const stageMeta = `${stages.length} ${stages.length === 1 ? 'stage' : 'stages'}`
    return {
      headline,
      badge: 'Overdue',
      meta: [options?.stageScoped ? overdueMeta : stageMeta, dueSoonMeta]
        .filter(Boolean)
        .join(' · '),
      target,
      ariaLabel: `${headline}. Oldest is ${target.label ?? target.actionId} for ${target.patientName}.`,
    }
  }

  const headline =
    dueSoon.length === 1
      ? `1 action is due soon${scope}`
      : `${dueSoon.length} actions are due soon${scope}`
  const stages = [...new Set(dueSoon.map((timer) => timer.stageId))]
  const stageMeta = `${stages.length} ${stages.length === 1 ? 'stage' : 'stages'}`
  return {
    headline,
    badge: 'Due soon',
    meta: options?.stageScoped ? `${dueSoon.length} due soon` : stageMeta,
    target,
    ariaLabel: `${headline}. Oldest is ${target.label ?? target.actionId} for ${target.patientName}.`,
  }
}

export function attentionClickTarget(timer: ActionTimer) {
  return {
    page: timer.stageId,
    stepId: timer.stepId,
    patientId: timer.patientId,
    patientName: timer.patientName,
  }
}
