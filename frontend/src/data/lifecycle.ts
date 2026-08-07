import {
  pickFacility,
  providersInCity,
  requireCaseManager,
} from './wcw'
import type { LifecycleCase, LifecycleStage, LifecycleStageId } from './lifecycleTypes'

export type {
  LifecycleCase,
  LifecycleCaseStatus,
  LifecycleStage,
  LifecycleStageId,
} from './lifecycleTypes'

export const LIFECYCLE_STAGES: LifecycleStage[] = [
  {
    id: 'assignment',
    label: 'Case-manager assignment',
    description: 'Match patient location to the approved territory list and propose the case manager.',
    beforeCount: 9,
    afterVerb: 'assignments prepared',
    runLabel: 'Assign case managers',
  },
  {
    id: 'provider',
    label: 'Provider selection',
    description: 'Suggest the company provider that covers the patient territory.',
    beforeCount: 7,
    afterVerb: 'providers suggested',
    runLabel: 'Confirm providers',
  },
  {
    id: 'scheduling',
    label: 'Route-aware scheduling',
    description: 'Read the routing schedule and present appointment windows that fit the route.',
    beforeCount: 6,
    afterVerb: 'windows prepared',
    runLabel: 'Prepare schedule windows',
  },
  {
    id: 'provider_response',
    label: 'One-hour provider-response monitoring',
    description: 'Watch the one-hour confirmation window and flag unanswered referrals.',
    beforeCount: 3,
    afterVerb: 'response timers monitored',
    runLabel: 'Run response check',
  },
  {
    id: 'end_of_day',
    label: 'End-of-day unscheduled referral check',
    description: 'Scan active referrals after the deadline and assemble one exception list.',
    beforeCount: 2,
    afterVerb: 'end-of-day exceptions prepared',
    runLabel: 'Run end-of-day check',
  },
  {
    id: 'weekly_visits',
    label: 'Weekly visit monitoring',
    description: 'Organize seen and not-seen outcomes from recorded visit statuses.',
    beforeCount: 18,
    afterVerb: 'visit outcomes organized',
    runLabel: 'Process visit outcomes',
  },
  {
    id: 'not_seen',
    label: 'Three consecutive not-seen escalation',
    description: 'Count consecutive missed visits and prepare noncompliance review requests.',
    beforeCount: 1,
    afterVerb: 'noncompliance reviews prepared',
    runLabel: 'Escalate not-seen cases',
  },
  {
    id: 'holds',
    label: 'Hold and return monitoring',
    description: 'Remove held patients from active scheduling and surface return-ready cases.',
    beforeCount: 4,
    afterVerb: 'hold movements processed',
    runLabel: 'Process holds',
  },
  {
    id: 'healed_expired',
    label: 'Healed/expired review',
    description: 'Detect recorded healed or expired statuses and start the human review path.',
    beforeCount: 2,
    afterVerb: 'clinical-status reviews opened',
    runLabel: 'Open clinical reviews',
  },
  {
    id: 'qa_discharge',
    label: 'QA and discharge approval',
    description: 'Prepare QA and discharge-approval packages without discharging automatically.',
    beforeCount: 1,
    afterVerb: 'approval packages prepared',
    runLabel: 'Prepare approval packages',
  },
]

function cm(name: string) {
  return requireCaseManager(name)
}

function providerNear(city: string, index = 0) {
  const list = providersInCity(city, index + 1)
  return list[Math.min(index, list.length - 1)] ?? providersInCity('Burbank', 1)[0]
}

export function createInitialLifecycleCases(): LifecycleCase[] {
  const braxton = cm('Braxton Rickert')
  const carla = cm('Carla Bustillo')
  const charlie = cm('Charlie Catado')
  const cole = cm('Cole Winfield')
  const daisy = cm('Daisy Trujillo')
  const erika = cm('Erika Rentoy')
  const farrah = cm('Farrah Go')
  const kim = cm('Kim Lopez')
  const nicole = cm('Nicole Chorvat')
  const tyler = cm('Tyler Manee')

  const reedProvider = providerNear('Downey', 0)
  const johnsonA = providerNear('Gardena', 0)
  const johnsonB = providerNear('Gardena', 1)
  const anaheimFacility = pickFacility('Anaheim Healthcare Center', 'Anaheim Crown Plaza')
  const burbankFacility = pickFacility('Burbank Retirement Villa', 'Belmont Village Senior Living - Burbank')
  const longBeachProvider = providerNear('Long Beach', 0)

  return [
    {
      id: 'lc-assign-1',
      patientName: 'Maria Alvarez',
      stageId: 'assignment',
      summary: 'Riverside ZIP matched to one territory',
      detail: `Suggested case manager: ${braxton.name} · Inland Empire · ${braxton.email}`,
      owner: `Intake → ${braxton.name}`,
      status: 'pending',
      minutesReturned: 8,
      actionLabel: 'Assign case manager',
      resultLabel: `${braxton.name} assigned`,
    },
    {
      id: 'lc-assign-2',
      patientName: 'James Carter',
      stageId: 'assignment',
      summary: 'Long Beach ZIP matched to one territory',
      detail: `Suggested case manager: ${carla.name} · Coastal LA · ${carla.email}`,
      owner: `Intake → ${carla.name}`,
      status: 'pending',
      minutesReturned: 8,
      actionLabel: 'Assign case manager',
      resultLabel: `${carla.name} assigned`,
    },
    {
      id: 'lc-provider-1',
      patientName: 'Thomas Reed',
      stageId: 'provider',
      summary: 'Downey territory has a clear company-provider match',
      detail: `Suggested provider: ${reedProvider.name} · ${reedProvider.city}${reedProvider.npi ? ` · NPI ${reedProvider.npi}` : ''}`,
      owner: charlie.name,
      status: 'pending',
      minutesReturned: 11,
      actionLabel: 'Confirm provider',
      resultLabel: `${reedProvider.name} selected`,
    },
    {
      id: 'lc-provider-2',
      patientName: 'Patricia Johnson',
      stageId: 'provider',
      summary: 'Gardena coverage unclear — two nearby providers',
      detail: `Flagged for human selection between ${johnsonA.name} (${johnsonA.city}) and ${johnsonB.name} (${johnsonB.city})`,
      owner: cole.name,
      status: 'pending',
      minutesReturned: 6,
      actionLabel: 'Open provider review',
      resultLabel: 'Human provider review opened',
    },
    {
      id: 'lc-sched-1',
      patientName: 'Maria Alvarez',
      stageId: 'scheduling',
      summary: 'Three route-fit windows found within 48 hours',
      detail: `Thu 10:20 AM · Thu 2:45 PM · Fri 9:15 AM · assigned CM ${braxton.name}`,
      owner: braxton.name,
      status: 'pending',
      minutesReturned: 14,
      actionLabel: 'Present schedule options',
      resultLabel: 'Schedule options sent to CM',
    },
    {
      id: 'lc-sched-2',
      patientName: 'James Carter',
      stageId: 'scheduling',
      summary: 'Route-aware slots prepared for Coastal LA',
      detail: `Fri 11:00 AM and Sat 8:40 AM remain · facility context ${anaheimFacility.name}`,
      owner: carla.name,
      status: 'pending',
      minutesReturned: 13,
      actionLabel: 'Present schedule options',
      resultLabel: 'Schedule options sent to CM',
    },
    {
      id: 'lc-resp-1',
      patientName: 'Thomas Reed',
      stageId: 'provider_response',
      summary: 'Provider confirmation timer at 47 minutes',
      detail: `Awaiting ${reedProvider.name} · CM ${charlie.name} will place on best-fit slot if the hour expires`,
      owner: 'Response monitor',
      status: 'monitoring',
      minutesReturned: 9,
      actionLabel: 'Escalate unanswered provider',
      resultLabel: 'One-hour exception prepared for CM',
    },
    {
      id: 'lc-resp-2',
      patientName: 'Patricia Johnson',
      stageId: 'provider_response',
      summary: 'Provider confirmed in 18 minutes',
      detail: `${johnsonA.name} accepted Fri 11:00 AM · Monday.com appointment date ready to write`,
      owner: 'Response monitor',
      status: 'pending',
      minutesReturned: 10,
      actionLabel: 'Record provider confirmation',
      resultLabel: 'Appointment confirmation recorded',
    },
    {
      id: 'lc-eod-1',
      patientName: 'Evelyn Brooks',
      stageId: 'end_of_day',
      summary: 'Still unscheduled after end-of-day deadline',
      detail: `Blocker: unclear phone pending partner callback · CM ${daisy.name}`,
      owner: 'Lead / management',
      status: 'pending',
      minutesReturned: 16,
      actionLabel: 'Add to exception list',
      resultLabel: 'Escalation package prepared',
    },
    {
      id: 'lc-eod-2',
      patientName: 'Linda Nguyen',
      stageId: 'end_of_day',
      summary: 'Unscheduled because insurance follow-up remains open',
      detail: `${erika.name} owns the missing-insurance request · facility ${burbankFacility.name}`,
      owner: 'Lead / management',
      status: 'pending',
      minutesReturned: 15,
      actionLabel: 'Add to exception list',
      resultLabel: 'Escalation package prepared',
    },
    {
      id: 'lc-week-1',
      patientName: 'Helen Park',
      stageId: 'weekly_visits',
      summary: 'Weekly visit recorded as SEEN in DRK',
      detail: `Initial visit completed by ${longBeachProvider.name} · consecutive not-seen counter reset`,
      owner: farrah.name,
      status: 'pending',
      minutesReturned: 7,
      actionLabel: 'Process seen outcome',
      resultLabel: 'Seen status synchronized',
    },
    {
      id: 'lc-week-2',
      patientName: 'Samuel Ortiz',
      stageId: 'weekly_visits',
      summary: 'Weekly visit recorded as NOT SEEN',
      detail: `Returned to next weekly cycle · consecutive not-seen = 2 · CM ${kim.name}`,
      owner: kim.name,
      status: 'pending',
      minutesReturned: 7,
      actionLabel: 'Process not-seen outcome',
      resultLabel: 'Not-seen counter updated',
    },
    {
      id: 'lc-ns-1',
      patientName: 'Gloria Bennett',
      stageId: 'not_seen',
      summary: 'Three consecutive weeks not seen',
      detail: `Noncompliance discharge-review request ready for ${nicole.name} and upper management`,
      owner: `${nicole.name} + management`,
      status: 'pending',
      minutesReturned: 22,
      actionLabel: 'Create discharge-review request',
      resultLabel: 'Noncompliance review opened',
    },
    {
      id: 'lc-hold-1',
      patientName: 'Arthur Kim',
      stageId: 'holds',
      summary: 'Hospitalization hold recorded',
      detail: `Removed from active weekly schedule · Hold Date captured · CM ${tyler.name}`,
      owner: tyler.name,
      status: 'pending',
      minutesReturned: 8,
      actionLabel: 'Move to holds list',
      resultLabel: 'Patient moved to holds',
    },
    {
      id: 'lc-hold-2',
      patientName: 'Rosa Delgado',
      stageId: 'holds',
      summary: 'Ready to return from vacation hold',
      detail: `Return flagged by ${cole.name} · weekly cycle can resume`,
      owner: cole.name,
      status: 'pending',
      minutesReturned: 9,
      actionLabel: 'Return to weekly cycle',
      resultLabel: 'Returned to weekly schedule',
    },
    {
      id: 'lc-heal-1',
      patientName: 'Margaret Ellis',
      stageId: 'healed_expired',
      summary: 'Wound healed status recorded by provider',
      detail: `QA review request prepared · provider ${providerNear('Burbank', 2).name} · no automatic discharge`,
      owner: `${charlie.name} → QA`,
      status: 'pending',
      minutesReturned: 12,
      actionLabel: 'Open healed QA review',
      resultLabel: 'Healed QA review prepared',
    },
    {
      id: 'lc-exp-1',
      patientName: 'Walter Grant',
      stageId: 'healed_expired',
      summary: 'Expired status recorded by authorized staff',
      detail: `Removed from future scheduling pending discharge approval · CM ${daisy.name}`,
      owner: `${daisy.name} → management`,
      status: 'pending',
      minutesReturned: 12,
      actionLabel: 'Open expired discharge review',
      resultLabel: 'Expired discharge review prepared',
    },
    {
      id: 'lc-qa-1',
      patientName: 'Margaret Ellis',
      stageId: 'qa_discharge',
      summary: 'QA package awaiting management approval',
      detail: `Discharge remains blocked until approval is recorded · prepared for ${nicole.name}`,
      owner: `QA + ${nicole.name}`,
      status: 'awaiting_human',
      minutesReturned: 18,
      actionLabel: 'Approve for management review',
      resultLabel: 'Approval package ready for management',
    },
  ]
}

export function lifecycleRunLabel(stageId: LifecycleStageId): string {
  return LIFECYCLE_STAGES.find((stage) => stage.id === stageId)?.runLabel ?? 'Run stage'
}
