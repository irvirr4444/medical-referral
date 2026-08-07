import { addMetrics, formatMinutes, WORKFLOW_TAB_MINUTES } from './constants'
import type { FlowOpsPageId } from './flowOps'
import type { BatchMetrics } from '../types'
import type { WorkflowScenario } from './scenarioTypes'

/** Totals already earned before today (through Thursday, Aug 6, 2026). */
export const IMPACT_PRIOR: {
  weekExcludingToday: BatchMetrics
  monthExcludingToday: BatchMetrics
} = {
  weekExcludingToday: {
    emailsReceived: 71,
    pdfsProcessed: 71,
    pagesAnalyzed: 964,
    valuesExtracted: 1388,
    requiredFieldsEvaluated: 497,
    duplicateSearches: 71,
    mondayPreviewsGenerated: 68,
    drkDraftsGenerated: 66,
    destinationReady: 52,
    incompleteOrUnclear: 11,
    probableDuplicatesBlocked: 5,
    readyForConfirmation: 48,
    manualActionsAvoided: 532,
    timeReturnedMinutes: 1988,
  },
  monthExcludingToday: {
    emailsReceived: 104,
    pdfsProcessed: 104,
    pagesAnalyzed: 1412,
    valuesExtracted: 2036,
    requiredFieldsEvaluated: 728,
    duplicateSearches: 104,
    mondayPreviewsGenerated: 99,
    drkDraftsGenerated: 97,
    destinationReady: 78,
    incompleteOrUnclear: 16,
    probableDuplicatesBlocked: 7,
    readyForConfirmation: 71,
    manualActionsAvoided: 786,
    timeReturnedMinutes: 2912,
  },
}

/** Share of referrals that typically reach each stage (demo funnel). */
const STAGE_FUNNEL: Record<FlowOpsPageId, number> = {
  intake: 1,
  handoff: 0.88,
  assignment: 0.86,
  provider: 0.8,
  scheduling: 0.74,
  'end-of-day': 0.92,
  weekly: 1.15,
}

export const IMPACT_STAGES: FlowOpsPageId[] = [
  'intake',
  'handoff',
  'assignment',
  'provider',
  'scheduling',
  'end-of-day',
  'weekly',
]

export type ImpactScope = FlowOpsPageId | 'overview'
export type ImpactPeriodId = 'today' | 'week' | 'month'

export interface ImpactStat {
  value: number
  label: string
}

export interface PeriodImpactView {
  id: ImpactPeriodId
  label: string
  caption: string
  timeLabel: string
  timeMinutes: number
  patients: number
  patientLabel: string
  stats: ImpactStat[]
}

interface StageImpactCopy {
  title: string
  blurb: string
  patientLabel: string
  stats: Array<{
    label: string
    value: (metrics: BatchMetrics, patients: number) => number
  }>
}

const STAGE_COPY: Record<FlowOpsPageId, StageImpactCopy> = {
  intake: {
    title: 'Intake impact',
    blurb: 'Time returned by extraction, verification, duplicate search, and destination prep.',
    patientLabel: 'Referrals processed',
    stats: [
      { label: 'PDF pages read', value: (m) => m.pagesAnalyzed },
      {
        label: 'Monday.com + DRK prepared',
        value: (m) => m.mondayPreviewsGenerated + m.drkDraftsGenerated,
      },
      { label: 'Duplicates blocked', value: (m) => m.probableDuplicatesBlocked },
      { label: 'Incomplete caught early', value: (m) => m.incompleteOrUnclear },
      { label: 'Manual actions avoided', value: (m) => m.manualActionsAvoided },
      { label: 'Ready for confirmation', value: (m) => m.readyForConfirmation },
    ],
  },
  handoff: {
    title: 'Handoff impact',
    blurb: 'Time returned by acknowledgements, Monday.com handoff rows, and DRK destination writes.',
    patientLabel: 'Handoffs prepared',
    stats: [
      { label: 'Monday.com rows prepared', value: (m) => m.mondayPreviewsGenerated },
      { label: 'DRK drafts prepared', value: (m) => m.drkDraftsGenerated },
      { label: 'Destinations ready', value: (m) => m.destinationReady },
      {
        label: 'Acknowledgements drafted',
        value: (_m, patients) => Math.round(patients * 0.9),
      },
      {
        label: 'Handoff events recorded',
        value: (_m, patients) => Math.round(patients * 1.4),
      },
      {
        label: 'Manual sends avoided',
        value: (_m, patients) => Math.round(patients * 3.2),
      },
    ],
  },
  assignment: {
    title: 'Assignment impact',
    blurb: 'Time returned by territory matching and case-manager suggestion.',
    patientLabel: 'Assignments prepared',
    stats: [
      {
        label: 'One-match suggestions',
        value: (_m, patients) => Math.round(patients * 0.72),
      },
      {
        label: 'Multi-match reviews',
        value: (_m, patients) => Math.round(patients * 0.18),
      },
      {
        label: 'No-match escalations',
        value: (_m, patients) => Math.round(patients * 0.1),
      },
      {
        label: 'Territory lookups avoided',
        value: (_m, patients) => Math.round(patients * 4),
      },
      {
        label: 'CM confirms completed',
        value: (_m, patients) => Math.round(patients * 0.8),
      },
      {
        label: 'Manual routing steps skipped',
        value: (_m, patients) => Math.round(patients * 5),
      },
    ],
  },
  provider: {
    title: 'Provider selection impact',
    blurb: 'Time returned by company-provider matching and coverage exception flags.',
    patientLabel: 'Provider matches prepared',
    stats: [
      {
        label: 'Clear provider suggestions',
        value: (_m, patients) => Math.round(patients * 0.68),
      },
      {
        label: 'Ambiguous reviews opened',
        value: (_m, patients) => Math.round(patients * 0.2),
      },
      {
        label: 'No-coverage escalations',
        value: (_m, patients) => Math.round(patients * 0.12),
      },
      {
        label: 'Roster searches avoided',
        value: (_m, patients) => Math.round(patients * 6),
      },
      {
        label: 'Send-status held for humans',
        value: (_m, patients) => Math.round(patients * 0.55),
      },
      {
        label: 'Manual list checks skipped',
        value: (_m, patients) => Math.round(patients * 4.5),
      },
    ],
  },
  scheduling: {
    title: 'Scheduling impact',
    blurb: 'Time returned by route windows, response timers, and confirmation monitoring.',
    patientLabel: 'Scheduling cases monitored',
    stats: [
      {
        label: 'Route windows offered',
        value: (_m, patients) => Math.round(patients * 1.6),
      },
      {
        label: 'One-hour timers watched',
        value: (_m, patients) => Math.round(patients * 0.85),
      },
      {
        label: 'Confirmations recorded',
        value: (_m, patients) => Math.round(patients * 0.7),
      },
      {
        label: 'Unanswered escalations',
        value: (_m, patients) => Math.round(patients * 0.15),
      },
      {
        label: 'Schedule lookups avoided',
        value: (_m, patients) => Math.round(patients * 5),
      },
      {
        label: 'Follow-up checks avoided',
        value: (_m, patients) => Math.round(patients * 3),
      },
    ],
  },
  'end-of-day': {
    title: 'End-of-day impact',
    blurb: 'Time returned by deadline scans and one management exception list.',
    patientLabel: 'Active referrals scanned',
    stats: [
      {
        label: 'Unscheduled exceptions found',
        value: (m) => Math.max(m.incompleteOrUnclear, Math.round(m.pdfsProcessed * 0.12)),
      },
      {
        label: 'Field conflicts flagged',
        value: (_m, patients) => Math.round(patients * 0.08),
      },
      {
        label: 'CM follow-ups prepared',
        value: (_m, patients) => Math.round(patients * 0.14),
      },
      {
        label: 'Management list items',
        value: (_m, patients) => Math.round(patients * 0.1),
      },
      {
        label: 'Manual board audits avoided',
        value: (_m, patients) => Math.round(patients * 2.5),
      },
      {
        label: 'Spreadsheet updates avoided',
        value: (_m, patients) => Math.round(patients * 2),
      },
    ],
  },
  weekly: {
    title: 'Weekly cycle impact',
    blurb: 'Time returned by visit tracking, holds, healed/expired paths, and discharge prep.',
    patientLabel: 'Weekly patients tracked',
    stats: [
      {
        label: 'Visit outcomes organized',
        value: (_m, patients) => Math.round(patients * 0.9),
      },
      {
        label: 'Missed-visit counts updated',
        value: (_m, patients) => Math.round(patients * 0.22),
      },
      {
        label: 'Hold movements processed',
        value: (_m, patients) => Math.round(patients * 0.12),
      },
      {
        label: 'QA / discharge reviews prepared',
        value: (_m, patients) => Math.round(patients * 0.08),
      },
      {
        label: 'Return-ready re-entries',
        value: (_m, patients) => Math.round(patients * 0.06),
      },
      {
        label: 'Manual tracker updates avoided',
        value: (_m, patients) => Math.round(patients * 4),
      },
    ],
  },
}

const OVERVIEW_COPY = {
  title: 'Impact',
  blurb: 'Time returned across every workflow stage — stage boards add up to these totals.',
  patientLabel: 'Patients processed',
}

export function impactBoardCopy(scope: ImpactScope) {
  if (scope === 'overview') return OVERVIEW_COPY
  return {
    title: STAGE_COPY[scope].title,
    blurb: STAGE_COPY[scope].blurb,
    patientLabel: STAGE_COPY[scope].patientLabel,
  }
}

function stagePatients(metrics: BatchMetrics, stage: FlowOpsPageId): number {
  return Math.max(1, Math.round(metrics.pdfsProcessed * STAGE_FUNNEL[stage]))
}

/** Split total minutes across stages by WORKFLOW_TAB_MINUTES weights; exact sum. */
export function allocateStageMinutes(totalMinutes: number): Record<FlowOpsPageId, number> {
  const weights = IMPACT_STAGES.map((stage) => WORKFLOW_TAB_MINUTES[stage] ?? 0)
  const weightSum = weights.reduce((sum, weight) => sum + weight, 0) || 1
  const exact = IMPACT_STAGES.map((stage, index) => ({
    stage,
    value: (totalMinutes * weights[index]) / weightSum,
  }))
  const floors = exact.map((item) => ({
    stage: item.stage,
    base: Math.floor(item.value),
    frac: item.value - Math.floor(item.value),
  }))
  let remaining = totalMinutes - floors.reduce((sum, item) => sum + item.base, 0)
  floors
    .slice()
    .sort((a, b) => b.frac - a.frac)
    .forEach((item) => {
      if (remaining <= 0) return
      item.base += 1
      remaining -= 1
    })
  return Object.fromEntries(floors.map((item) => [item.stage, item.base])) as Record<
    FlowOpsPageId,
    number
  >
}

export function completedMinutesByStage(
  scenarios: WorkflowScenario[],
): Record<FlowOpsPageId, number> {
  const totals = Object.fromEntries(IMPACT_STAGES.map((stage) => [stage, 0])) as Record<
    FlowOpsPageId,
    number
  >
  for (const scenario of scenarios) {
    for (const item of scenario.cases) {
      if (item.status !== 'completed' && item.status !== 'escalated') continue
      totals[scenario.tab] += item.minutesReturned
    }
  }
  return totals
}

function buildOverviewPeriod(
  id: ImpactPeriodId,
  label: string,
  caption: string,
  metrics: BatchMetrics,
  extraMinutes: number,
): PeriodImpactView {
  const timeMinutes = metrics.timeReturnedMinutes + extraMinutes
  return {
    id,
    label,
    caption,
    timeLabel: formatMinutes(timeMinutes),
    timeMinutes,
    patients: metrics.pdfsProcessed,
    patientLabel: OVERVIEW_COPY.patientLabel,
    stats: [
      { value: metrics.pagesAnalyzed, label: 'PDF pages read' },
      {
        value: metrics.mondayPreviewsGenerated + metrics.drkDraftsGenerated,
        label: 'Monday.com + DRK prepared',
      },
      { value: metrics.probableDuplicatesBlocked, label: 'Duplicates blocked' },
      { value: metrics.incompleteOrUnclear, label: 'Incomplete caught early' },
      { value: metrics.manualActionsAvoided, label: 'Manual actions avoided' },
      { value: metrics.readyForConfirmation, label: 'Ready for confirmation' },
    ],
  }
}

function buildStagePeriod(
  id: ImpactPeriodId,
  label: string,
  caption: string,
  metrics: BatchMetrics,
  stage: FlowOpsPageId,
  allocatedMinutes: number,
  extraMinutes: number,
): PeriodImpactView {
  const copy = STAGE_COPY[stage]
  const patients = stagePatients(metrics, stage)
  const timeMinutes = allocatedMinutes + extraMinutes
  return {
    id,
    label,
    caption,
    timeLabel: formatMinutes(timeMinutes),
    timeMinutes,
    patients,
    patientLabel: copy.patientLabel,
    stats: copy.stats.map((stat) => ({
      label: stat.label,
      value: Math.max(0, stat.value(metrics, patients)),
    })),
  }
}

export function buildPeriodImpacts(
  today: BatchMetrics,
  scope: ImpactScope = 'overview',
  extrasByStage: Partial<Record<FlowOpsPageId, number>> = {},
): PeriodImpactView[] {
  const week = addMetrics(IMPACT_PRIOR.weekExcludingToday, today)
  const month = addMetrics(IMPACT_PRIOR.monthExcludingToday, today)
  const extraTotal = IMPACT_STAGES.reduce(
    (sum, stage) => sum + (extrasByStage[stage] ?? 0),
    0,
  )

  const periodDefs: Array<{
    id: ImpactPeriodId
    label: string
    caption: string
    metrics: BatchMetrics
  }> = [
    { id: 'today', label: 'Today', caption: 'Friday, August 7', metrics: today },
    { id: 'week', label: 'This week', caption: 'Mon–Fri week to date', metrics: week },
    { id: 'month', label: 'This month', caption: 'August to date', metrics: month },
  ]

  if (scope === 'overview') {
    return periodDefs.map((period) =>
      buildOverviewPeriod(
        period.id,
        period.label,
        period.caption,
        period.metrics,
        extraTotal,
      ),
    )
  }

  return periodDefs.map((period) => {
    const allocated = allocateStageMinutes(period.metrics.timeReturnedMinutes)
    return buildStagePeriod(
      period.id,
      period.label,
      period.caption,
      period.metrics,
      scope,
      allocated[scope],
      extrasByStage[scope] ?? 0,
    )
  })
}
