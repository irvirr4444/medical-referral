import type { FlowOpsPageId } from '../../../../data/flowOps'
import type { ArtifactField, ArtifactSection } from '../../types'
import {
  isHandoffOperationStep,
} from '../../combinedAssignment'

type StepEvidence = {
  received: string
  produced: string
  evidence: string
  fields: ArtifactField[]
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
    ],
    steps: {
      'notify-referral-source': receipt(
        'Approved referral and source contact',
        'Acknowledgment delivered',
        'Outlook message ACK-8821',
        [
          field('Recipient', 'Riverside Home Health', 'Outlook To'),
          field('Delivery status', 'Delivered at 10:04 AM', 'Outlook'),
        ],
      ),
      'create-monday-record': receipt(
        'Approved patient fields',
        'Monday item 5816018427 created',
        '8 fields verified by read-back',
        [
          field('Patient name', 'Maria Alvarez', 'Name'),
          field('Date of birth', '02/14/1958', 'Patient DoB'),
          field('Phone', '(555) 014-2381', 'Phone'),
          field('Address', '4821 Palm Grove Dr, Riverside, CA', 'Patient Address'),
          field('Agency', 'Riverside Home Health', 'Company'),
          field('Wound information', 'Lower-leg wound evaluation', 'Wound / Clinical Info'),
          field('Insurance', 'Medicare', 'Insurance'),
          field('Intake status', 'In intake', 'Stage'),
        ],
      ),
      'create-update-drk': receipt(
        'Approved referral and duplicate-clear result',
        'DRK chart 204918 created',
        'Browser receipt DRK-204918',
        [
          field('Patient', 'Maria Alvarez', 'DRK Patient Name'),
          field('DOB', '02/14/1958', 'DRK Date of Birth'),
          field('Insurance', 'Medicare', 'DRK Insurance'),
          field('Referral PDF', 'REF-2026-0810-1042.pdf', 'DRK Documents'),
          field('Chart ID', '204918', 'DRK Chart ID'),
        ],
      ),
      'verify-handoff': receipt(
        'Monday.com and DRK receipts',
        'Handoff verified',
        'Destination values agree',
        [
          field('Monday.com item', '5816018427', 'Verified'),
          field('DRK chart', '204918', 'Verified'),
          field('Handoff status', 'Complete', 'Workflow status'),
        ],
      ),
    },
  },
  assignment: {
    patientId: 'marcus-feldman',
    patientName: 'Marcus Feldman',
    referralId: 'REF-2026-0810-0930',
    context: [
      { label: 'Service address', value: '1718 W 162nd St, Gardena, CA 90247' },
      { label: 'Referral completeness', value: 'Complete' },
    ],
    steps: {
      'determine-owner': receipt(
        'Location, source, and missing fields',
        'Cole Ramirez recommended',
        'South Bay territory rule v12',
        [
          field('Routing branch', 'Case manager', 'Assignment rule'),
          field('Territory', 'South Bay', 'Coverage area'),
          field('Recommended owner', 'Cole Ramirez', 'Owner candidate'),
        ],
      ),
      'assign-owner': receipt(
        'Cole Ramirez and routing reason',
        'Awaiting owner selection and write',
        'Human gate ASSIGN-0930',
        [
          field('Monday.com owner', 'Cole Ramirez', 'Case Manager'),
          field('DRK owner', 'Cole Ramirez', 'Assigned Case Manager'),
        ],
      ),
    },
  },
  provider: {
    patientId: 'helen-park',
    patientName: 'Helen Park',
    referralId: 'REF-2026-0810-0850',
    context: [
      { label: 'Service area', value: 'Torrance, CA 90503' },
      { label: 'Care need', value: 'Lower-leg wound evaluation' },
    ],
    steps: {
      'find-eligible-providers': receipt(
        'Location, care need, and active roster',
        '3 eligible providers found',
        'WCW Provider Board updated 8:45 AM',
        [
          field('Service area', 'Torrance, CA 90503', 'Provider search'),
          field('Eligible providers', '3', 'Candidate count'),
          field('Excluded providers', '2', 'Outside coverage'),
        ],
      ),
      'select-provider': receipt(
        '3 eligible providers',
        'Dr. Sofia Lee recommended',
        '4.2 miles; wound care; capacity available',
        [
          field('Recommended provider', 'Dr. Sofia Lee', 'Provider selection'),
          field('Match reason', 'Coverage, distance, capacity', 'Selection reason'),
        ],
      ),
      'record-provider': receipt(
        'Dr. Lee and two alternatives',
        'Awaiting provider selection and write',
        'Human gate PROVIDER-0850',
        [
          field('Monday.com provider', 'Dr. Sofia Lee', 'Provider'),
          field('DRK provider', 'Dr. Sofia Lee', 'Rendering Provider'),
        ],
      ),
    },
  },
  scheduling: {
    patientId: 'maria-alvarez',
    patientName: 'Maria Alvarez',
    referralId: 'REF-2026-0810-1042',
    context: [
      { label: 'Selected provider', value: 'Dr. Sofia Lee' },
      { label: 'Target', value: 'Visit within 24-48 hours' },
    ],
    steps: {
      'send-referral-provider': receipt(
        'Approved referral and selected provider',
        'Referral delivered to Dr. Lee',
        'Delivery receipt 10:06 AM',
        [
          field('Provider', 'Dr. Sofia Lee', 'Referral recipient'),
          field('Referral sent', 'August 10 at 10:06 AM', 'Referral Sent to Provider'),
        ],
      ),
      'capture-provider-response': receipt(
        'Provider delivery and response window',
        'Provider accepted; two slots available',
        'Response received at 10:24 AM',
        [
          field('Provider response', 'Accepted', 'Response status'),
          field('Available slots', 'Aug 11 10:00 AM; Aug 12 1:30 PM', 'Availability'),
        ],
      ),
      'confirm-record-appointment': receipt(
        'Two route-compatible appointment choices',
        'Awaiting slot selection and write',
        'Idempotency key APPT-MA-1042',
        [
          field('Monday.com appointment', '08/11/2026 10:00 AM', 'Appointment Date'),
          field('DRK appointment', '08/11/2026 10:00 AM', 'Appointment'),
        ],
      ),
      'verify-scheduling': receipt(
        'Appointment write receipts',
        'Scheduling complete',
        'Monday.com and DRK values agree',
        [
          field('Scheduled status', 'Scheduled', 'Monday.com'),
          field('Scheduling complete', 'Yes', 'Monday.com'),
        ],
      ),
    },
  },
  'end-of-day': {
    patientId: 'frank-owens',
    patientName: 'Frank Owens',
    referralId: 'REF-2026-0810-0724',
    context: [
      { label: 'Case manager', value: 'Ana Torres' },
      { label: 'Scheduling due', value: 'August 10 by 5:00 PM' },
    ],
    steps: {
      'find-unscheduled': receipt(
        'Active referrals due by 5:00 PM',
        'Frank Owens requires follow-up',
        'Monday.com and DRK contain no appointment',
        [
          field('Scheduled status', 'Not scheduled', 'Monday.com'),
          field('Blocker', 'Provider response overdue', 'Scheduling blocker'),
          field('Responsible owner', 'Ana Torres', 'Case Manager'),
        ],
      ),
      'notify-owner': receipt(
        'Patient, owner, and blocker',
        'Lead and Ana notified',
        'Delivered at 5:01 PM',
        [
          field('Recipients', 'Ana Torres; Intake Lead', 'Notification'),
          field('Follow-up status', 'Delivered', 'Workflow status'),
        ],
      ),
      'escalate-unresolved': receipt(
        'Unresolved blocker and follow-up history',
        'Escalation to Nicole prepared',
        'Exception EOD-FRANK-0810',
        [
          field('Escalation owner', 'Nicole', 'Management owner'),
          field('Escalation reason', 'Provider response overdue', 'Reason'),
        ],
      ),
      'verify-resolution': receipt(
        'Refreshed appointment fields',
        'Patient remains unscheduled',
        'Weekly-cycle entry held',
        [
          field('Final scheduling state', 'Unresolved', 'Workflow status'),
          field('Weekly-cycle entry', 'Held', 'Next action'),
        ],
      ),
    },
  },
  weekly: {
    patientId: 'arthur-kim',
    patientName: 'Arthur Kim',
    referralId: 'PAT-DRK-198204',
    context: [
      { label: 'Visit date', value: 'August 10, 2026' },
      { label: 'Provider', value: 'Dr. Sofia Lee' },
    ],
    steps: {
      'record-visit-outcome': receipt(
        'Current DRK progress note',
        'Visit recorded as Not Seen',
        'Hospitalization note at 4:42 PM',
        [
          field('Visit status', 'Not Seen', 'Monday.com Visit Status'),
          field('Source note', 'Hospitalized', 'DRK progress note'),
        ],
      ),
      'apply-weekly-rules': receipt(
        'Not Seen plus previous patient state',
        'Hospitalization hold identified',
        'Hold suppresses Not Seen increment',
        [
          field('Patient status', 'On hold - hospitalized', 'Patient Status'),
          field('Consecutive Not Seen', '1 - unchanged', 'Not Seen Count'),
          field('Required action', 'Hold review', 'Workflow action'),
        ],
      ),
      'assign-follow-up': receipt(
        'Hold review and supporting note',
        'Hold-team action assigned',
        'Existing action updated; no duplicate',
        [
          field('Assigned team', 'WCW Hold Team', 'Follow-up owner'),
          field('Action', 'Review hospitalization hold', 'Follow-up type'),
        ],
      ),
      'verify-weekly-result': receipt(
        'Status write and follow-up receipt',
        'Weekly cycle remains open',
        'Awaiting explicit return-to-care update',
        [
          field('Cycle state', 'Open - on hold', 'Workflow status'),
          field('Next check', 'Next weekly monitor', 'Monitor schedule'),
        ],
      ),
    },
  },
}

function field(label: string, value: string, destination: string): ArtifactField {
  return { label, value, meta: destination }
}

function receipt(
  received: string,
  produced: string,
  evidence: string,
  fields: ArtifactField[],
): StepEvidence {
  return { received, produced, evidence, fields }
}

function heroLookup(
  stageId: FlowOpsPageId,
  patientId: string,
  stepId: string,
): { story?: HeroStory; evidence?: StepEvidence } {
  const lookupStage: FlowOpsPageId = isHandoffOperationStep(stepId)
    ? 'handoff'
    : stageId === 'handoff'
      ? 'assignment'
      : stageId
  const lookupStep =
    stepId === 'assign-owner' && lookupStage === 'assignment'
      ? HERO_STORIES.assignment?.steps['determine-owner']
        ? 'determine-owner'
        : 'assign-owner'
      : stepId
  const story = HERO_STORIES[lookupStage]
  if (!story || story.patientId !== patientId) return {}
  return { story, evidence: story.steps[lookupStep] }
}

function heroEvidence(
  stageId: FlowOpsPageId,
  patientId: string,
  stepId: string,
): StepEvidence | undefined {
  return heroLookup(stageId, patientId, stepId).evidence
}

export function heroPatientIdForStage(stageId: FlowOpsPageId): string | undefined {
  if (stageId === 'assignment') {
    return HERO_STORIES.assignment?.patientId
  }
  return HERO_STORIES[stageId]?.patientId
}

export function heroActionFields(
  stageId: FlowOpsPageId,
  patientId: string,
  stepId: string,
): ArtifactField[] | undefined {
  return heroEvidence(stageId, patientId, stepId)?.fields
}

export function heroArtifactSections(
  stageId: FlowOpsPageId,
  patientId: string,
  stepId: string,
): ArtifactSection[] | undefined {
  const { story, evidence } = heroLookup(stageId, patientId, stepId)
  if (!story || !evidence) return undefined

  return [
    {
      id: 'technical-details',
      title: 'Technical details',
      fields: [
        { label: 'Referral / chart ID', value: story.referralId },
        { label: 'Input', value: evidence.received },
        { label: 'Output', value: evidence.produced },
        { label: 'Evidence', value: evidence.evidence },
        ...story.context,
      ],
    },
  ]
}
