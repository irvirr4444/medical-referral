/** Boss-facing overview and stage metrics. Values are illustrative demo data. */

import type { FlowOpsPageId } from './flowOps'

export type BossPeriodId = 'today' | 'week' | 'month' | 'custom'
export type BossMetricsScope = 'overview' | FlowOpsPageId

export interface BossMetricCard {
  id: string
  label: string
  meaning: string
  value: number
  previousValue: number
  delta: number
  deltaPercent: number
}

export interface BossPeriodView {
  id: BossPeriodId
  label: string
  caption: string
  comparisonLabel: string
  comparisonHoverLabel: string
  metrics: BossMetricCard[]
}

export interface BossMetricDefinition {
  id: string
  label: string
  meaning: string
}

/** Anchored to the demo operating day used across the console. */
export const BOSS_DEMO_TODAY = '2026-08-07'

const PERIOD_ORDER: Array<Exclude<BossPeriodId, 'custom'>> = [
  'today',
  'week',
  'month',
]

const PERIOD_META: Record<
  Exclude<BossPeriodId, 'custom'>,
  {
    label: string
    caption: string
    comparisonLabel: string
    comparisonHoverLabel: string
  }
> = {
  today: {
    label: 'Today',
    caption: 'Friday, August 7, 2026',
    comparisonLabel: 'vs yesterday',
    comparisonHoverLabel: 'Compared to last day',
  },
  week: {
    label: 'This week',
    caption: 'Monday–Friday, August 3–7, 2026',
    comparisonLabel: 'vs last week',
    comparisonHoverLabel: 'Compared to last week',
  },
  month: {
    label: 'This month',
    caption: 'August 1–7, 2026',
    comparisonLabel: 'vs prior month to date',
    comparisonHoverLabel: 'Compared to last month',
  },
}

type PeriodValues = Record<string, number>

interface ScopeMetricConfig {
  metrics: BossMetricDefinition[]
  presets: Record<
    Exclude<BossPeriodId, 'custom'>,
    { values: PeriodValues; previousValues: PeriodValues }
  >
  dailyRates: PeriodValues
  priorDailyRates: PeriodValues
}

function values(
  a: number,
  b: number,
  c: number,
  d: number,
  ids: string[],
): PeriodValues {
  return {
    [ids[0]]: a,
    [ids[1]]: b,
    [ids[2]]: c,
    [ids[3]]: d,
  }
}

function scopeConfig(
  metrics: BossMetricDefinition[],
  today: [number, number, number, number],
  todayPrev: [number, number, number, number],
  week: [number, number, number, number],
  weekPrev: [number, number, number, number],
  month: [number, number, number, number],
  monthPrev: [number, number, number, number],
  daily: [number, number, number, number],
  priorDaily: [number, number, number, number],
): ScopeMetricConfig {
  const ids = metrics.map((metric) => metric.id)
  return {
    metrics,
    presets: {
      today: {
        values: values(...today, ids),
        previousValues: values(...todayPrev, ids),
      },
      week: {
        values: values(...week, ids),
        previousValues: values(...weekPrev, ids),
      },
      month: {
        values: values(...month, ids),
        previousValues: values(...monthPrev, ids),
      },
    },
    dailyRates: values(...daily, ids),
    priorDailyRates: values(...priorDaily, ids),
  }
}

const SCOPE_CONFIG: Record<BossMetricsScope, ScopeMetricConfig> = {
  overview: scopeConfig(
    [
      {
        id: 'new-referrals',
        label: 'New referrals',
        meaning: 'Referrals received during the selected period.',
      },
      {
        id: 'patients-scheduled',
        label: 'Patients scheduled',
        meaning: 'Referrals with a confirmed appointment date.',
      },
      {
        id: 'patients-seen',
        label: 'Patients seen',
        meaning: 'Patients marked SEEN after a completed visit.',
      },
      {
        id: 'wounds-healed',
        label: 'Wounds healed',
        meaning: 'Patients discharged because treatment was completed.',
      },
    ],
    [18, 14, 42, 3],
    [15, 16, 39, 2],
    [82, 61, 198, 11],
    [94, 58, 186, 13],
    [126, 94, 286, 17],
    [118, 101, 274, 15],
    [16, 12, 38, 2.2],
    [14.5, 11.2, 35, 2],
  ),
  intake: scopeConfig(
    [
      {
        id: 'referrals-received',
        label: 'Referrals received',
        meaning: 'New referral PDFs that arrived in the info box.',
      },
      {
        id: 'ready-to-proceed',
        label: 'Ready to proceed',
        meaning: 'Referrals with name, date of birth, phone, and address confirmed.',
      },
      {
        id: 'waiting-on-information',
        label: 'Waiting on information',
        meaning: 'Referrals that cannot move forward until missing details are returned.',
      },
      {
        id: 'escalated-to-marketer',
        label: 'Escalated to marketer',
        meaning: 'Referrals sent to the assigned marketer because the partner was unreachable or critical information was missing.',
      },
    ],
    [18, 14, 3, 1],
    [15, 12, 2, 1],
    [82, 65, 12, 5],
    [94, 70, 16, 8],
    [126, 102, 18, 6],
    [118, 95, 16, 7],
    [16, 12.5, 2.4, 0.8],
    [14.5, 11.5, 2.8, 1],
  ),
  handoff: scopeConfig(
    [
      {
        id: 'patients-handed-off',
        label: 'Patients handed off',
        meaning: 'Patients transferred from intake into case-manager ownership.',
      },
      {
        id: 'sources-acknowledged',
        label: 'Sources acknowledged',
        meaning: 'Referral sources that received a thank-you and confirmation email.',
      },
      {
        id: 'case-managers-notified',
        label: 'Case managers notified',
        meaning: 'Case managers who received the referral PDF for their territory.',
      },
      {
        id: 'charts-started',
        label: 'Charts started',
        meaning: 'Patients with a DRK chart started by the face-sheet team.',
      },
    ],
    [14, 14, 14, 13],
    [12, 12, 12, 11],
    [65, 63, 65, 61],
    [70, 68, 70, 66],
    [102, 98, 102, 96],
    [95, 92, 95, 90],
    [12.5, 12, 12.5, 11.8],
    [11.5, 11, 11.5, 10.8],
  ),
  assignment: scopeConfig(
    [
      {
        id: 'patients-assigned',
        label: 'Patients assigned',
        meaning: 'Patients assigned to a case manager based on location.',
      },
      {
        id: 'waiting-on-assignment',
        label: 'Waiting on assignment',
        meaning: 'Patients still waiting for a case manager to be assigned.',
      },
      {
        id: 'ready-for-provider-selection',
        label: 'Ready for provider selection',
        meaning: 'Assigned patients whose case can move to provider selection.',
      },
      {
        id: 'needs-review',
        label: 'Needs review',
        meaning: 'Patients with unclear territory coverage that need a person to choose the owner.',
      },
    ],
    [13, 1, 11, 1],
    [12, 2, 9, 2],
    [61, 4, 52, 4],
    [66, 5, 55, 5],
    [96, 6, 84, 6],
    [90, 7, 79, 7],
    [11.8, 0.8, 10.2, 0.8],
    [10.8, 1, 9.4, 1],
  ),
  provider: scopeConfig(
    [
      {
        id: 'providers-confirmed',
        label: 'Providers confirmed',
        meaning: 'Patients matched to an approved provider for their area.',
      },
      {
        id: 'waiting-on-provider',
        label: 'Waiting on provider',
        meaning: 'Patients waiting for the provider to confirm availability.',
      },
      {
        id: 'no-coverage',
        label: 'No coverage',
        meaning: 'Patients with no available provider in range, escalated for review.',
      },
      {
        id: 'sent-to-provider',
        label: 'Referrals sent to provider',
        meaning: 'Referrals marked as sent to the selected provider.',
      },
    ],
    [10, 2, 1, 10],
    [9, 1, 2, 9],
    [48, 7, 4, 48],
    [50, 8, 6, 50],
    [74, 10, 6, 74],
    [70, 9, 8, 70],
    [9, 1.4, 0.8, 9],
    [8.4, 1.2, 1.1, 8.4],
  ),
  scheduling: scopeConfig(
    [
      {
        id: 'patients-scheduled',
        label: 'Patients scheduled',
        meaning: 'Patients with a confirmed appointment date on the schedule.',
      },
      {
        id: 'scheduled-within-48h',
        label: 'Scheduled within 48 hours',
        meaning:
          'Patients who got an appointment date within 48 hours after the referral was ready to schedule.',
      },
      {
        id: 'waiting-to-schedule',
        label: 'Waiting to schedule',
        meaning: 'Patients still waiting for an appointment to be set.',
      },
      {
        id: 'overdue-to-schedule',
        label: 'Overdue to schedule',
        meaning: 'Patients past the expected scheduling window without an appointment.',
      },
    ],
    [14, 11, 3, 1],
    [12, 10, 4, 2],
    [61, 49, 12, 5],
    [58, 46, 14, 6],
    [94, 78, 16, 7],
    [88, 72, 18, 9],
    [12, 9.5, 2.4, 0.9],
    [11.2, 8.8, 2.8, 1.1],
  ),
  'end-of-day': scopeConfig(
    [
      {
        id: 'scheduled-by-cutoff',
        label: 'Scheduled by end of day',
        meaning: 'Patients who had a confirmed appointment before the daily review.',
      },
      {
        id: 'unscheduled-at-cutoff',
        label: 'Still unscheduled',
        meaning: 'Patients who still had no appointment when the team reviewed scheduling at the end of the day.',
      },
      {
        id: 'cleared-after-follow-up',
        label: 'Resolved without escalation',
        meaning: 'Scheduling issues resolved by the lead and case manager without involving management.',
      },
      {
        id: 'escalated-to-management',
        label: 'Escalated to management',
        meaning: 'Unresolved unscheduled cases sent to Nicole or upper management.',
      },
    ],
    [15, 3, 2, 1],
    [12, 4, 3, 1],
    [70, 12, 9, 3],
    [80, 14, 10, 4],
    [110, 16, 12, 4],
    [100, 18, 13, 5],
    [13.5, 2.4, 1.8, 0.6],
    [12.2, 2.8, 2, 0.8],
  ),
  weekly: scopeConfig(
    [
      {
        id: 'patients-seen',
        label: 'Patients seen',
        meaning: 'Patients with a completed weekly visit marked SEEN.',
      },
      {
        id: 'missed-visits',
        label: 'Missed visits',
        meaning: 'Patients marked NOT seen and needing reschedule.',
      },
      {
        id: 'patients-on-hold',
        label: 'Placed on hold',
        meaning: 'Patients placed on hold during the selected period because of hospitalization, vacation, or another temporary reason.',
      },
      {
        id: 'ready-for-discharge',
        label: 'Discharge reviews needed',
        meaning: 'Patients needing discharge review for healed, expired, or repeated noncompliance.',
      },
    ],
    [42, 6, 4, 3],
    [39, 8, 5, 2],
    [198, 28, 18, 11],
    [186, 32, 16, 13],
    [286, 41, 24, 17],
    [274, 46, 22, 15],
    [38, 5.2, 3.4, 2.2],
    [35, 5.8, 3.1, 2],
  ),
}

function deltaPercent(value: number, previousValue: number): number {
  if (previousValue === 0) return value === 0 ? 0 : 100
  return Math.round(((value - previousValue) / previousValue) * 100)
}

function cardsFromValues(
  definitions: BossMetricDefinition[],
  current: PeriodValues,
  previous: PeriodValues,
): BossMetricCard[] {
  return definitions.map((definition) => {
    const value = current[definition.id] ?? 0
    const previousValue = previous[definition.id] ?? 0
    return {
      id: definition.id,
      label: definition.label,
      meaning: definition.meaning,
      value,
      previousValue,
      delta: value - previousValue,
      deltaPercent: deltaPercent(value, previousValue),
    }
  })
}

function parseIsoDate(value: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null
  const [year, month, day] = value.split('-').map(Number)
  const date = new Date(Date.UTC(year, month - 1, day))
  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  ) {
    return null
  }
  return date
}

function formatCaption(start: Date, end: Date): string {
  const formatter = new Intl.DateTimeFormat('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  })
  if (start.getTime() === end.getTime()) {
    return formatter.format(start)
  }
  return `${formatter.format(start)} – ${formatter.format(end)}`
}

export function inclusiveDayCount(startIso: string, endIso: string): number | null {
  const start = parseIsoDate(startIso)
  const end = parseIsoDate(endIso)
  if (!start || !end || end < start) return null
  const msPerDay = 24 * 60 * 60 * 1000
  return Math.floor((end.getTime() - start.getTime()) / msPerDay) + 1
}

export function buildCustomBossMetrics(
  startIso: string,
  endIso: string,
  scope: BossMetricsScope = 'overview',
): BossPeriodView | null {
  const start = parseIsoDate(startIso)
  const end = parseIsoDate(endIso)
  const days = inclusiveDayCount(startIso, endIso)
  if (!start || !end || days === null) return null

  const config = SCOPE_CONFIG[scope]
  const current = Object.fromEntries(
    config.metrics.map((metric) => [
      metric.id,
      Math.max(0, Math.round((config.dailyRates[metric.id] ?? 0) * days)),
    ]),
  )
  const previous = Object.fromEntries(
    config.metrics.map((metric) => [
      metric.id,
      Math.max(0, Math.round((config.priorDailyRates[metric.id] ?? 0) * days)),
    ]),
  )

  return {
    id: 'custom',
    label: 'Custom range',
    caption: formatCaption(start, end),
    comparisonLabel: 'vs prior period',
    comparisonHoverLabel: 'Compared to the prior period',
    metrics: cardsFromValues(config.metrics, current, previous),
  }
}

export function buildBossPeriodViews(
  scope: BossMetricsScope = 'overview',
): BossPeriodView[] {
  const config = SCOPE_CONFIG[scope]
  return PERIOD_ORDER.map((id) => ({
    id,
    label: PERIOD_META[id].label,
    caption: PERIOD_META[id].caption,
    comparisonLabel: PERIOD_META[id].comparisonLabel,
    comparisonHoverLabel: PERIOD_META[id].comparisonHoverLabel,
    metrics: cardsFromValues(
      config.metrics,
      config.presets[id].values,
      config.presets[id].previousValues,
    ),
  }))
}

export function bossPeriodById(
  id: Exclude<BossPeriodId, 'custom'>,
  scope: BossMetricsScope = 'overview',
): BossPeriodView {
  return buildBossPeriodViews(scope).find((period) => period.id === id)!
}

export function emptyBossPeriodView(
  scope: BossMetricsScope = 'overview',
): BossPeriodView {
  return {
    id: 'custom',
    label: 'Custom range',
    caption: 'Choose a start and end date.',
    comparisonLabel: 'vs prior period',
    comparisonHoverLabel: 'Compared to the prior period',
    metrics: bossPeriodById('today', scope).metrics.map((metric) => ({
      ...metric,
      value: 0,
      previousValue: 0,
      delta: 0,
      deltaPercent: 0,
    })),
  }
}

export function formatMetricDelta(delta: number): string {
  if (delta > 0) return `+${delta}`
  return `${delta}`
}

/** Kept for older overview tests and imports. */
export const BOSS_METRIC_DEFINITIONS = SCOPE_CONFIG.overview.metrics
