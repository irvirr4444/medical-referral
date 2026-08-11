import type { FlowOpsPageId } from '../../../../data/flowOps'
import type { ArtifactSection } from '../../types'

type StepEvidence = {
  received: string
  produced: string
  evidence: string
}

type HeroStory = {
  patientId: string
  patientName: string
  referralId: string
  context: Array<{ label: string; value: string }>
  steps: Record<string, StepEvidence>
}

const HERO_STORIES: Partial<Record<FlowOpsPageId, HeroStory>> = {
  handoff: {
    patientId: 'maria-alvarez',
    patientName: 'Maria Alvarez',
    referralId: 'REF-2026-0810-1042',
    context: [
      { label: 'Referral source', value: 'Riverside Home Health' },
      { label: 'Approved by', value: 'Braxton - Intake' },
      { label: 'Required fields', value: '7 of 7 confirmed' },
      { label: 'Duplicate result', value: 'No Monday or DRK match' },
    ],
    steps: {
      'load-approved-plan': receipt('Approved referral v3', 'Locked handoff plan', 'Approval CONF-1042'),
      'map-monday-fields': receipt('Referral source and reviewer contacts', 'Acknowledgment sent; CM copied', 'Outlook message ACK-8821'),
      'resolve-agency': receipt('Complete referral and territory context', 'Routed to Ana Torres and Face Sheet Team', 'Routing rule Riverside-02'),
      'write-monday': receipt('Explicit Master Sheet column payload', 'Monday item 5816018427 created', '8 columns verified by read-back'),
      'prepare-drk': receipt('Demographics, insurance, and wound summary', 'DRK Create Patient draft ready', '12 mapped fields; 0 unresolved'),
      'apply-drk': receipt('Approved DRK draft', 'DRK chart 204918 created', 'Browser receipt DRK-204918'),
      'link-destinations': receipt('Monday 5816018427 and DRK 204918', 'Cross-system patient link stored', 'Link PAT-MA-1042'),
      'reconcile-handoff': receipt('Destination receipts and patient link', 'Handoff verified', 'Monday and DRK values agree'),
    },
  },
  assignment: {
    patientId: 'marcus-feldman',
    patientName: 'Marcus Feldman',
    referralId: 'REF-2026-0810-0930',
    context: [
      { label: 'Service address', value: '1718 W 162nd St, Gardena, CA 90247' },
      { label: 'Referral completeness', value: 'Complete - normal CM branch' },
      { label: 'Referral source', value: 'South Bay Physician Group' },
      { label: 'Current owner', value: 'Unassigned' },
    ],
    steps: {
      'load-assignment-context': receipt('Linked referral and service address', 'Assignment context ready', 'Address and source verified'),
      'normalize-location': receipt('Gardena residential address', 'Gardena, 90247, residence', 'USPS-normalized location'),
      'load-territories': receipt('Territory rules v12', 'South Bay coverage rules loaded', 'Rules active August 1, 2026'),
      'match-owner': receipt('90247 and active staff roster', 'Cole Ramirez ranked first', 'Territory match; active caseload 18'),
      'classify-assignment': receipt('Complete referral and ranked candidates', 'Case-manager branch selected', 'No missing-info marketer follow-up'),
      'confirm-assignment': receipt('Cole recommendation and match evidence', 'Awaiting WCW confirmation', 'Human gate ASSIGN-0930'),
      'write-assignment': receipt('Confirmed owner', 'Monday and DRK owner fields ready', 'Destination write plan ASSIGN-0930'),
    },
  },
  provider: {
    patientId: 'helen-park',
    patientName: 'Helen Park',
    referralId: 'REF-2026-0810-0850',
    context: [
      { label: 'Service area', value: 'Torrance, CA 90503' },
      { label: 'Care need', value: 'Lower-leg wound evaluation' },
      { label: 'Case manager', value: 'Cole Ramirez' },
      { label: 'Insurance', value: 'Medicare' },
    ],
    steps: {
      'load-provider-context': receipt('Patient, location, and wound summary', 'Provider search context ready', 'Clinical source linked to referral PDF'),
      'load-provider-roster': receipt('Approved roster updated 8:45 AM', '5 active South Bay providers', 'Roster source WCW Provider Board'),
      'filter-providers': receipt('Coverage, capability, and service radius', '3 eligible; 2 excluded', 'Exclusions show radius and availability'),
      'rank-providers': receipt('3 eligible providers', 'Dr. Lee ranked first', '4.2 miles; wound care; capacity available'),
      'classify-provider-result': receipt('Ranked shortlist', 'Clear recommendation', 'No coverage gap or ambiguity'),
      'confirm-provider': receipt('Dr. Lee plus two alternatives', 'Awaiting case-manager confirmation', 'Human gate PROVIDER-0850'),
      'write-provider': receipt('Confirmed provider', 'Monday and DRK updates ready', 'Read-back required after write'),
    },
  },
  scheduling: {
    patientId: 'maria-alvarez',
    patientName: 'Maria Alvarez',
    referralId: 'REF-2026-0810-1042',
    context: [
      { label: 'Selected provider', value: 'Dr. Sofia Lee' },
      { label: 'Patient availability', value: 'Weekdays after 9:00 AM' },
      { label: 'Service address', value: '4821 Palm Grove Dr, Riverside' },
      { label: 'Target', value: 'Visit within 24-48 hours' },
    ],
    steps: {
      'load-scheduling-context': receipt('Confirmed provider and patient contact', 'Scheduling context ready', 'Phone and address verified'),
      'read-availability': receipt('Approved referral package', 'Referral delivered to Dr. Lee', 'Delivery receipt 10:06 AM'),
      'generate-windows': receipt('Delivery receipt and 11:06 AM deadline', 'Awaiting provider response', 'Response timer active'),
      'present-windows': receipt('Provider response and route', 'Tuesday and Wednesday availability read', 'Schedule observed 10:24 AM'),
      'monitor-response': receipt('Availability and route constraints', 'Two appointment options ranked', 'Both options inside 48-hour target'),
      'classify-response': receipt('Two appointment options', 'Human appointment decision required', 'No destination write before confirmation'),
      'write-appointment': receipt('Confirmed date and time', 'Monday and DRK payloads ready', 'Idempotency key APPT-MA-1042'),
      'reconcile-appointment': receipt('Write receipts and expected slot', 'Scheduling read-back pending', 'Expected values must agree'),
    },
  },
  'end-of-day': {
    patientId: 'frank-owens',
    patientName: 'Frank Owens',
    referralId: 'REF-2026-0810-0724',
    context: [
      { label: 'Case manager', value: 'Ana Torres' },
      { label: 'Scheduling due', value: 'August 10, 2026 by 5:00 PM' },
      { label: 'Appointment state', value: 'No confirmed appointment' },
      { label: 'Current blocker', value: 'Provider response overdue' },
    ],
    steps: {
      'start-eod-cycle': receipt('5:00 PM cutoff and healthy readers', 'EOD cycle EOD-0810 opened', 'Monday and DRK sources current'),
      'load-due-referrals': receipt('Active referrals due today', 'Frank Owens included', 'Incomplete scheduling detected'),
      'read-eod-sources': receipt('Monday item and DRK chart', 'Ana Torres; provider response overdue', 'Both systems lack an appointment'),
      'normalize-scheduling': receipt('Patient, owner, and blocker', 'Lead and Ana notified', 'Notification delivered at 5:01 PM'),
      'dedupe-eod-alerts': receipt('Follow-up and refreshed status', 'Blocker remains unresolved', 'Single active follow-up retained'),
      'create-eod-exceptions': receipt('Unresolved follow-up history', 'Escalation to Nicole prepared', 'Exception EOD-FRANK-0810'),
      'notify-eod': receipt('Refreshed Monday and DRK state', 'Patient still unscheduled', 'No explicit appointment evidence'),
      'resolve-eod': receipt('Unresolved scheduling exception', 'Weekly-cycle entry held', 'Scheduling must be verified first'),
    },
  },
  weekly: {
    patientId: 'arthur-kim',
    patientName: 'Arthur Kim',
    referralId: 'PAT-DRK-198204',
    context: [
      { label: 'Visit date', value: 'August 10, 2026' },
      { label: 'Provider', value: 'Dr. Sofia Lee' },
      { label: 'Previous Not Seen count', value: '1' },
      { label: 'Current patient state', value: 'Hospitalized - hold review' },
    ],
    steps: {
      'start-weekly-cycle': receipt('Weekly cursor and healthy source status', 'Arthur Kim loaded for review', 'Expected visit activity found'),
      'read-visit-status': receipt('DRK chart 198204', 'Hospitalization note found', 'Progress note recorded August 10 at 4:42 PM'),
      'normalize-visit-status': receipt('Hospitalization note and visit record', 'Visit marked Not Seen', 'Explicit visit outcome retained'),
      'detect-visit-change': receipt('Visit result and previous state', 'Hospitalization hold identified', 'Hold prevents discharge-count action'),
      'update-not-seen-counter': receipt('Not Seen plus active hold', 'Counter remains 1', 'Hold policy suppresses increment'),
      'classify-weekly-review': receipt('Hold state and source evidence', 'Hold tracking review required', 'No automatic clinical decision'),
      'create-weekly-exception': receipt('Review classification', 'Hold-team action prepared', 'Owner: WCW hold team'),
      'notify-and-reconcile': receipt('Open hold action', 'Awaiting human follow-up', 'Resolution requires a later explicit source update'),
    },
  },
}

function receipt(received: string, produced: string, evidence: string): StepEvidence {
  return { received, produced, evidence }
}

export function heroPatientIdForStage(stageId: FlowOpsPageId): string | undefined {
  return HERO_STORIES[stageId]?.patientId
}

export function heroArtifactSections(
  stageId: FlowOpsPageId,
  patientId: string,
  stepId: string,
): ArtifactSection[] | undefined {
  const story = HERO_STORIES[stageId]
  const evidence = story?.steps[stepId]
  if (!story || story.patientId !== patientId || !evidence) return undefined

  return [
    {
      id: 'patient-context',
      title: 'Patient and referral context',
      fields: [
        { label: 'Patient', value: story.patientName },
        { label: 'Referral / chart ID', value: story.referralId },
        ...story.context,
      ],
    },
    {
      id: 'step-receipt',
      title: 'What this step received and produced',
      defaultExpanded: true,
      fields: [
        { label: 'Input received', value: evidence.received },
        { label: 'Output produced', value: evidence.produced },
        { label: 'Evidence / receipt', value: evidence.evidence },
      ],
    },
  ]
}
