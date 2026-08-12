import type { FlowOpsPageId } from './flowOps'
import type { ScenarioCase, ScenarioCaseStatus, WorkflowScenario } from './scenarioTypes'
import type { ReferralRecord } from '../types'
import { formatMinutes } from './constants'

export interface JourneyStepDef {
  stage: FlowOpsPageId
  caseId: string
  shortLabel: string
  stageLabel: string
}

export interface JourneyPatientDef {
  id: string
  patientName: string
  referralId: string | null
  context: string
  /** Current real-world scenario shown on the roster. */
  scenarioLabel: string
  /** Stage index where this patient is waiting when the day starts. */
  stuckAtIndex: number
  steps: JourneyStepDef[]
}

export const JOURNEY_STAGE_ORDER: FlowOpsPageId[] = [
  'intake',
  'assignment',
  'handoff',
  'provider',
  'scheduling',
  'end-of-day',
  'weekly',
]

const STAGE_LABELS: Record<FlowOpsPageId, string> = {
  intake: 'Intake',
  handoff: 'Handoff',
  assignment: 'Assignment',
  provider: 'Provider',
  scheduling: 'Scheduling',
  'end-of-day': 'End-of-day',
  weekly: 'Weekly',
}

function step(
  stage: FlowOpsPageId,
  caseId: string,
  shortLabel: string,
): JourneyStepDef {
  return { stage, caseId, shortLabel, stageLabel: STAGE_LABELS[stage] }
}

const DEFAULT_STAGE_ACTIONS: Record<FlowOpsPageId, string> = {
  intake: 'Confirm referral',
  handoff: 'Verify handoff',
  assignment: 'Confirm assignment',
  provider: 'Confirm provider',
  scheduling: 'Confirm schedule',
  'end-of-day': 'Clear exception',
  weekly: 'Record weekly outcome',
}

function snapshotPatient({
  id,
  patientName,
  context,
  scenarioLabel,
  stage,
  caseId,
  actionLabel,
}: {
  id: string
  patientName: string
  context: string
  scenarioLabel: string
  stage: FlowOpsPageId
  caseId: string
  actionLabel: string
}): JourneyPatientDef {
  const stuckAtIndex = JOURNEY_STAGE_ORDER.indexOf(stage)
  return {
    id,
    patientName,
    referralId: null,
    context,
    scenarioLabel,
    stuckAtIndex,
    steps: JOURNEY_STAGE_ORDER.map((stepStage) =>
      step(
        stepStage,
        stepStage === stage ? caseId : `journey-${id}-${stepStage}`,
        stepStage === stage ? actionLabel : DEFAULT_STAGE_ACTIONS[stepStage],
      ),
    ),
  }
}

/**
 * Realistic in-flight census. The first seven retain full named paths; additional
 * patients anchor to real exception/approval cases throughout the workflow.
 */
export const JOURNEY_PATIENTS: JourneyPatientDef[] = [
  {
    id: 'maria-alvarez',
    patientName: 'Maria Alvarez',
    referralId: 'maria-alvarez',
    context: 'Sunrise Home Health · Riverside · Braxton Rickert',
    scenarioLabel: 'Acknowledgement prepared',
    stuckAtIndex: 1,
    steps: [
      step('intake', 'in-ready-1', 'Confirm referral'),
      step('handoff', 'ho-ack-1', 'Review acknowledgement'),
      step('assignment', 'ho-one-1', 'Assign Braxton'),
      step('provider', 'sc-one-3', 'Confirm provider'),
      step('scheduling', 'sc-win-1', 'Present windows'),
      step('end-of-day', 'eod-ok-1', 'Verify scheduled'),
      step('weekly', 'wk-seen-2', 'Weekly SEEN'),
    ],
  },
  {
    id: 'james-carter',
    patientName: 'James Carter',
    referralId: 'james-carter',
    context: 'Oak Valley Hospital · Coastal LA · Carla Bustillo',
    scenarioLabel: 'Monday.com / DRK operation outcomes',
    stuckAtIndex: 1,
    steps: [
      step('intake', 'in-recv-1', 'Verify fingerprint'),
      step('handoff', 'ho-dest-2', 'Retry DRK draft'),
      step('assignment', 'ho-one-2', 'Assign Carla'),
      step('provider', 'sc-one-4', 'Confirm provider'),
      step('scheduling', 'sc-win-2', 'Present windows'),
      step('end-of-day', 'eod-ok-3', 'Verify scheduled'),
      step('weekly', 'wk-seen-3', 'Weekly SEEN'),
    ],
  },
  {
    id: 'thomas-reed',
    patientName: 'Thomas Reed',
    referralId: 'thomas-reed',
    context: 'Lakeside Vascular · Downey · Charlie Catado',
    scenarioLabel: 'Physician referral ready',
    stuckAtIndex: 0,
    steps: [
      step('intake', 'in-ready-2', 'Confirm referral'),
      step('handoff', 'ho-dest-3', 'Verify destinations'),
      step('assignment', 'ho-one-3', 'Assign Charlie'),
      step('provider', 'sc-one-1', 'Confirm provider'),
      step('scheduling', 'sc-pend-1', 'Chase provider reply'),
      step('end-of-day', 'eod-ok-4', 'Verify scheduled'),
      step('weekly', 'wk-cont-1', 'Continue weekly'),
    ],
  },
  {
    id: 'helen-park',
    patientName: 'Helen Park',
    referralId: null,
    context: 'Anaheim Healthcare · Placentia route · Farrah Go',
    scenarioLabel: 'Provider selected but not contacted',
    stuckAtIndex: 3,
    steps: [
      step('intake', 'in-unreach-2', 'Escalate to marketer'),
      step('handoff', 'ho-dest-4', 'Verify destinations'),
      step('assignment', 'ho-one-4', 'Assign Farrah'),
      step('provider', 'sc-pend-2', 'Prepare provider send'),
      step('scheduling', 'sc-ok-2', 'Record acceptance'),
      step('end-of-day', 'eod-ok-5', 'Verify scheduled'),
      step('weekly', 'wk-seen-1', 'Weekly SEEN'),
    ],
  },
  {
    id: 'patricia-johnson',
    patientName: 'Patricia Johnson',
    referralId: 'patricia-johnson',
    context: 'Community Care · Cole Winfield',
    scenarioLabel: 'New source document received',
    stuckAtIndex: 0,
    steps: [
      step('intake', 'in-recv-2', 'Verify fingerprint'),
      step('handoff', 'ho-ack-3', 'Send acknowledgement'),
      step('assignment', 'ho-one-5', 'Assign Cole'),
      step('provider', 'sc-amb-1', 'Pick provider'),
      step('scheduling', 'sc-ok-1', 'Record acceptance'),
      step('end-of-day', 'eod-ok-2', 'Verify scheduled'),
      step('weekly', 'wk-cont-2', 'Continue weekly'),
    ],
  },
  {
    id: 'linda-nguyen',
    patientName: 'Linda Nguyen',
    referralId: 'linda-nguyen',
    context: 'Partner reachable · missing details · Braxton Rickert',
    scenarioLabel: 'Not eligible for handoff',
    stuckAtIndex: 1,
    steps: [
      step('intake', 'in-reach-1', 'Prepare follow-up'),
      step('handoff', 'ho-inelig-1', 'Hold handoff'),
      step('assignment', 'ho-one-6', 'Assign Charlie'),
      step('provider', 'sc-one-5', 'Confirm provider'),
      step('scheduling', 'sc-win-4', 'Present windows'),
      step('end-of-day', 'eod-inc-1', 'Fix inconsistent fields'),
      step('weekly', 'wk-cont-3', 'Continue weekly'),
    ],
  },
  {
    id: 'robert-williams',
    patientName: 'Robert Williams',
    referralId: 'robert-williams',
    context: 'Probable Monday.com duplicate · human review',
    scenarioLabel: 'Private review draft prepared',
    stuckAtIndex: 0,
    steps: [
      step('intake', 'in-draft-2', 'Open review draft'),
      step('handoff', 'ho-dest-5', 'Verify destinations'),
      step('assignment', 'ho-one-7', 'Assign Braxton'),
      step('provider', 'sc-one-6', 'Confirm provider'),
      step('scheduling', 'sc-win-5', 'Present windows'),
      step('end-of-day', 'eod-ok-6', 'Verify scheduled'),
      step('weekly', 'wk-ns1-1', 'Process not-seen'),
    ],
  },
  snapshotPatient({
    id: 'anita-gomez',
    patientName: 'Anita Gomez',
    context: 'Rancho Cucamonga SNF · Kim Lopez',
    scenarioLabel: 'Resolvable by CM / lead',
    stage: 'end-of-day',
    caseId: 'eod-res-1',
    actionLabel: 'Resolve with CM',
  }),
  snapshotPatient({
    id: 'irene-cho',
    patientName: 'Irene Cho',
    context: 'Belmont Village Burbank · Carla Bustillo',
    scenarioLabel: 'Ambiguous provider match',
    stage: 'provider',
    caseId: 'sc-amb-2',
    actionLabel: 'Open provider review',
  }),
  snapshotPatient({
    id: 'marcus-feldman',
    patientName: 'Marcus Feldman',
    context: 'Anaheim Crown Plaza · Nicole Chorvat',
    scenarioLabel: 'New ZIP absent from rules',
    stage: 'assignment',
    caseId: 'ho-none-2',
    actionLabel: 'Escalate unmatched ZIP',
  }),
  snapshotPatient({
    id: 'nancy-liu',
    patientName: 'Nancy Liu',
    context: 'South Gate Home Health · Carla Bustillo',
    scenarioLabel: 'No confirmation within one hour',
    stage: 'scheduling',
    caseId: 'sc-late-2',
    actionLabel: 'Escalate unanswered provider',
  }),
  snapshotPatient({
    id: 'david-ruiz',
    patientName: 'David Ruiz',
    context: 'Pasadena Wound Partners · Intake team',
    scenarioLabel: 'Facility vs residence conflict',
    stage: 'assignment',
    caseId: 'ho-multi-2',
    actionLabel: 'Choose case manager',
  }),
  snapshotPatient({
    id: 'frank-owens',
    patientName: 'Frank Owens',
    context: 'Los Angeles Home Health · Nicole Chorvat',
    scenarioLabel: 'Management escalation required',
    stage: 'end-of-day',
    caseId: 'eod-mgmt-1',
    actionLabel: 'Escalate to management',
  }),
  snapshotPatient({
    id: 'betty-hayes',
    patientName: 'Betty Hayes',
    context: 'Burbank Congregate Living · Nicole Chorvat',
    scenarioLabel: 'Facility outside active routes',
    stage: 'provider',
    caseId: 'sc-none-2',
    actionLabel: 'Escalate to Nicole',
  }),
  snapshotPatient({
    id: 'susan-park',
    patientName: 'Susan Park',
    context: 'Placentia Care Center · Daisy Trujillo',
    scenarioLabel: 'Already notified by Monday.com',
    stage: 'end-of-day',
    caseId: 'eod-note-1',
    actionLabel: 'Verify notification',
  }),
  snapshotPatient({
    id: 'george-chen',
    patientName: 'George Chen',
    context: 'Menifee Skilled Nursing · Management',
    scenarioLabel: 'Lead already notified',
    stage: 'end-of-day',
    caseId: 'eod-note-2',
    actionLabel: 'Verify notification',
  }),
  snapshotPatient({
    id: 'evelyn-brooks',
    patientName: 'Evelyn Brooks',
    context: 'Northstar Skilled Nursing · Daisy Trujillo',
    scenarioLabel: 'Required-field classification',
    stage: 'intake',
    caseId: 'in-field-4',
    actionLabel: 'Review gap',
  }),
  snapshotPatient({
    id: 'samuel-ortiz',
    patientName: 'Samuel Ortiz',
    context: 'Burbank Retirement Villa West · Kim Lopez',
    scenarioLabel: 'Partner unreachable',
    stage: 'intake',
    caseId: 'in-unreach-1',
    actionLabel: 'Escalate to marketer',
  }),
  snapshotPatient({
    id: 'gloria-bennett',
    patientName: 'Gloria Bennett',
    context: 'Weekly cycle · Nicole Chorvat + management',
    scenarioLabel: 'Third consecutive not-seen',
    stage: 'weekly',
    caseId: 'wk-ns3-1',
    actionLabel: 'Create discharge-review request',
  }),
  snapshotPatient({
    id: 'arthur-kim',
    patientName: 'Arthur Kim',
    context: 'Weekly cycle · Tyler Manee + management',
    scenarioLabel: 'Hold not ready to return',
    stage: 'weekly',
    caseId: 'wk-remain-1',
    actionLabel: 'Keep on holds',
  }),
  snapshotPatient({
    id: 'margaret-ellis',
    patientName: 'Margaret Ellis',
    context: 'Provider-recorded healed status · QA',
    scenarioLabel: 'Wound healed recorded',
    stage: 'weekly',
    caseId: 'wk-heal-1',
    actionLabel: 'Open healed QA review',
  }),
  snapshotPatient({
    id: 'walter-grant',
    patientName: 'Walter Grant',
    context: 'CM-recorded expired status · management',
    scenarioLabel: 'Expired status recorded',
    stage: 'weekly',
    caseId: 'wk-exp-1',
    actionLabel: 'Open expired discharge review',
  }),
  snapshotPatient({
    id: 'dorothy-lane',
    patientName: 'Dorothy Lane',
    context: 'Burbank Retirement Villa East · management',
    scenarioLabel: 'Facility-reported expired',
    stage: 'weekly',
    caseId: 'wk-exp-2',
    actionLabel: 'Open expired discharge review',
  }),
  snapshotPatient({
    id: 'rosa-delgado',
    patientName: 'Rosa Delgado',
    context: 'Belmont Village Burbank · Cole Winfield',
    scenarioLabel: 'Duplicate search outcomes',
    stage: 'intake',
    caseId: 'in-dup-3',
    actionLabel: 'Keep blocked',
  }),
]

/** @deprecated Prefer JOURNEY_PATIENTS[0] — kept for existing imports/tests. */
export const JOURNEY_PATIENT = JOURNEY_PATIENTS[0].patientName
export const JOURNEY_REFERRAL_ID = 'maria-alvarez'
export const MARIA_JOURNEY_STEPS = JOURNEY_PATIENTS[0].steps
export const DEFAULT_JOURNEY_PATIENT_ID = JOURNEY_PATIENTS[0].id

export const JOURNEY_CASE_IDS = new Set(
  JOURNEY_PATIENTS.flatMap((patient) => patient.steps.map((step) => step.caseId)),
)

/** Original open-state summaries for journey cases (restart restore). */
export const JOURNEY_OPEN_SUMMARIES: Record<string, string> = {
  'in-ready-1': 'Straight-through home-health referral',
  'ho-dest-1': 'Both destinations succeeded',
  'ho-one-1': 'Riverside ZIP → Braxton Rickert',
  'sc-one-3': 'Inland Empire provider suggested',
  'sc-win-1': 'Three Inland Empire windows',
  'eod-ok-1': 'Thursday appointment complete',
  'wk-seen-2': 'Weekly visit SEEN',
  'in-recv-1': 'Hospital discharge packet accepted once',
  'ho-dest-2': 'Monday ok · DRK retry needed',
  'ho-one-2': 'Long Beach ZIP → Carla Bustillo',
  'sc-one-4': 'Coastal LA provider suggested',
  'sc-win-2': 'Two Coastal LA windows',
  'eod-ok-3': 'Friday appointment complete',
  'wk-seen-3': 'Weekly visit SEEN',
  'in-ready-2': 'Physician-office referral ready',
  'ho-dest-3': 'DRK ok · Monday retry needed',
  'ho-one-3': 'Downey ZIP → Charlie Catado',
  'sc-one-1': 'Aaron Currie suggested for Downey',
  'eod-ok-4': 'Wednesday appointment complete',
  'wk-cont-1': 'Stable ongoing wound treatment',
  'in-unreach-2': 'Missing DOB — fax line busy',
  'ho-dest-4': 'Both destinations succeeded',
  'ho-one-4': 'Placentia ZIP → Farrah Go',
  'sc-one-2': 'Clear Anaheim route provider',
  'sc-ok-2': 'Confirmed in 47 minutes',
  'eod-ok-5': 'Tuesday appointment complete',
  'wk-seen-1': 'Weekly visit SEEN',
  'in-field-2': 'Home-health explicitly none',
  'ho-ack-3': 'Acknowledgement draft ready',
  'ho-one-5': 'Territory match → Cole Winfield',
  'sc-amb-1': 'Two Gardena-area providers',
  'sc-ok-1': 'Confirmed in 18 minutes',
  'sc-pend-1': 'Aaron Currie selected · send pending',
  'eod-ok-2': 'Friday appointment complete',
  'wk-cont-2': 'Follow-up after completed visit',
  'in-reach-1': 'Facility confirms payer on callback',
  'ho-ack-2': 'Corrected ack naming Kim Lopez',
  'ho-one-6': 'Burbank ZIP → Charlie Catado',
  'sc-one-5': 'Burbank-route provider suggested',
  'sc-win-4': 'Two Belmont windows',
  'eod-inc-1': 'Date present · status blank',
  'wk-cont-3': 'Remains on weekly schedule',
  'in-dup-2': 'Probable duplicate blocked',
  'ho-dest-5': 'Both destinations succeeded',
  'ho-one-7': 'Riverside ZIP → Braxton Rickert',
  'sc-one-6': 'Inland Empire provider suggested',
  'sc-win-5': 'Three Riverside windows',
  'eod-ok-6': 'Monday appointment complete',
  'wk-ns1-1': 'Week 1 not seen',
}

export interface JourneyStepView extends JourneyStepDef {
  caseItem: ScenarioCase | null
  status: ScenarioCaseStatus | 'missing'
  done: boolean
  actionLabel: string
  resultLabel: string
  summary: string
  minutesReturned: number
}

export interface PatientJourneyView {
  patientId: string
  patientName: string
  context: string
  referralId: string | null
  scenarioLabel: string
  stuckStageLabel: string
  steps: JourneyStepView[]
  current: JourneyStepView | null
  completedCount: number
  totalSteps: number
  minutesOnPath: number
  minutesLabel: string
  complete: boolean
}

export interface JourneyRosterItem {
  patient: JourneyPatientDef
  journey: PatientJourneyView
}

function findCase(scenarios: WorkflowScenario[], caseId: string): ScenarioCase | null {
  for (const scenario of scenarios) {
    const match = scenario.cases.find((item) => item.id === caseId)
    if (match) return match
  }
  return null
}

export function getJourneyPatient(patientId: string): JourneyPatientDef | null {
  return JOURNEY_PATIENTS.find((item) => item.id === patientId) ?? null
}

export function buildPatientJourney(
  scenarios: WorkflowScenario[],
  patientId: string = DEFAULT_JOURNEY_PATIENT_ID,
): PatientJourneyView {
  const patient = getJourneyPatient(patientId) ?? JOURNEY_PATIENTS[0]
  const steps: JourneyStepView[] = patient.steps.map((def) => {
    const caseItem = findCase(scenarios, def.caseId)
    const status = caseItem?.status ?? 'missing'
    const done = status === 'completed' || status === 'escalated'
    return {
      ...def,
      caseItem,
      status,
      done,
      actionLabel: caseItem?.actionLabel ?? def.shortLabel,
      resultLabel: caseItem?.resultLabel ?? def.shortLabel,
      summary: caseItem?.summary ?? def.shortLabel,
      minutesReturned: caseItem?.minutesReturned ?? 0,
    }
  })

  const current = steps.find((item) => !item.done) ?? null
  const completedCount = steps.filter((item) => item.done).length
  const minutesOnPath = steps
    .filter((item) => item.done)
    .reduce((sum, item) => sum + item.minutesReturned, 0)
  const stuckLabel =
    current?.stageLabel ??
    patient.steps[Math.min(patient.stuckAtIndex, patient.steps.length - 1)]?.stageLabel ??
    'Intake'

  return {
    patientId: patient.id,
    patientName: patient.patientName,
    context: patient.context,
    referralId: patient.referralId,
    scenarioLabel: patient.scenarioLabel,
    stuckStageLabel: stuckLabel,
    steps,
    current,
    completedCount,
    totalSteps: steps.length,
    minutesOnPath,
    minutesLabel: formatMinutes(minutesOnPath),
    complete: completedCount === steps.length,
  }
}

export function buildJourneyRoster(scenarios: WorkflowScenario[]): JourneyRosterItem[] {
  return JOURNEY_PATIENTS.map((patient) => ({
    patient,
    journey: buildPatientJourney(scenarios, patient.id),
  }))
}

export function referralForJourneyPatient(
  referrals: ReferralRecord[],
  patientId: string = DEFAULT_JOURNEY_PATIENT_ID,
): ReferralRecord | null {
  const patient = getJourneyPatient(patientId)
  if (!patient?.referralId) return null
  return referrals.find((item) => item.id === patient.referralId) ?? null
}

export function journeyStepByCaseId(
  caseId: string,
  patientId?: string,
): JourneyStepDef | null {
  if (patientId) {
    return getJourneyPatient(patientId)?.steps.find((step) => step.caseId === caseId) ?? null
  }
  for (const patient of JOURNEY_PATIENTS) {
    const match = patient.steps.find((step) => step.caseId === caseId)
    if (match) return match
  }
  return null
}

export function patientIdForJourneyCase(caseId: string): string | null {
  for (const patient of JOURNEY_PATIENTS) {
    if (patient.steps.some((step) => step.caseId === caseId)) return patient.id
  }
  return null
}

export function scenarioContainingCase(
  scenarios: WorkflowScenario[],
  caseId: string,
): WorkflowScenario | null {
  return scenarios.find((scenario) => scenario.cases.some((item) => item.id === caseId)) ?? null
}

export function sumCompletedJourneyCaseMinutes(
  scenarios: WorkflowScenario[],
  patientId?: string,
): number {
  const ids = patientId
    ? new Set(getJourneyPatient(patientId)?.steps.map((step) => step.caseId) ?? [])
    : JOURNEY_CASE_IDS
  let sum = 0
  for (const scenario of scenarios) {
    for (const item of scenario.cases) {
      if (!ids.has(item.id)) continue
      if (item.status === 'completed' || item.status === 'escalated') {
        sum += item.minutesReturned
      }
    }
  }
  return sum
}

/** Mark prior stages complete so each roster patient starts stuck mid-path. */
export function seedJourneyProgress(scenarios: WorkflowScenario[]): WorkflowScenario[] {
  const completedIds = new Set<string>()
  const upcomingIds = new Set<string>()
  for (const patient of JOURNEY_PATIENTS) {
    for (let i = 0; i < patient.stuckAtIndex; i += 1) {
      const caseId = patient.steps[i]?.caseId
      if (caseId) completedIds.add(caseId)
    }
    for (let i = patient.stuckAtIndex + 1; i < patient.steps.length; i += 1) {
      const caseId = patient.steps[i]?.caseId
      if (caseId) upcomingIds.add(caseId)
    }
  }

  return scenarios.map((scenario) => ({
    ...scenario,
    cases: scenario.cases.map((item) => {
      if (completedIds.has(item.id)) {
        return {
          ...item,
          status: 'completed' as const,
          summary: item.resultLabel,
        }
      }
      if (upcomingIds.has(item.id)) {
        return { ...item, status: 'upcoming' as const }
      }
      return item
    }),
  }))
}

export function reopenJourneyCases(
  scenarios: WorkflowScenario[],
  patientId?: string,
): WorkflowScenario[] {
  const ids = patientId
    ? new Set(getJourneyPatient(patientId)?.steps.map((step) => step.caseId) ?? [])
    : JOURNEY_CASE_IDS

  const reopened = scenarios.map((scenario) => ({
    ...scenario,
    cases: scenario.cases.map((item) => {
      if (!ids.has(item.id)) return item
      return {
        ...item,
        status: 'open' as const,
        summary:
          JOURNEY_OPEN_SUMMARIES[item.id] ??
          journeyStepByCaseId(item.id)?.shortLabel ??
          item.summary,
      }
    }),
  }))

  if (!patientId) return seedJourneyProgress(reopened)

  const patient = getJourneyPatient(patientId)
  if (!patient) return reopened
  const completedIds = new Set(
    patient.steps.slice(0, patient.stuckAtIndex).map((step) => step.caseId),
  )
  const upcomingIds = new Set(
    patient.steps.slice(patient.stuckAtIndex + 1).map((step) => step.caseId),
  )
  return reopened.map((scenario) => ({
    ...scenario,
    cases: scenario.cases.map((item) => {
      if (completedIds.has(item.id)) {
        return {
          ...item,
          status: 'completed' as const,
          summary: item.resultLabel,
        }
      }
      if (upcomingIds.has(item.id)) return { ...item, status: 'upcoming' as const }
      return item
    }),
  }))
}
