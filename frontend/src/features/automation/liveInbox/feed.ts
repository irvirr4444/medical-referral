import { parseOpsDate } from '../ops'
import type { PatientStepStatus, StepFeedDay, StepFeedRow } from '../ops/types'
import type { IntakeFeedDay, LiveInboxFeedRow, LiveInboxReferral } from './types'

export function mergeLiveInboxFeed({
  demoDays,
  referrals,
  drkDuplicateCheckEnabled,
  patientQuery = '',
  statuses,
  selectedStepId,
}: {
  demoDays: StepFeedDay[]
  referrals: LiveInboxReferral[]
  drkDuplicateCheckEnabled?: boolean
  patientQuery?: string
  statuses: PatientStepStatus[]
  selectedStepId: string
}): IntakeFeedDay[] {
  const query = patientQuery.trim().toLowerCase()
  const eligibleReferrals = referrals
  const liveRows: LiveInboxFeedRow[] = eligibleReferrals
    .filter((referral) => {
      if (!query) return true
      return [referral.subject, referral.sender, referral.filename]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(query))
    })
    .map((referral) => {
      const workflowStep = referral.steps[selectedStepId]
      const isReceipt = selectedStepId === 'receive-referral'
      const status: PatientStepStatus = isReceipt
        ? 'done'
        : workflowStep?.status ?? pendingStepStatus(referral, selectedStepId)
      return {
      patientId: `live-${referral.id}`,
      patientName: referral.patient_label || referral.subject || 'Pending patient identification',
      stepId: selectedStepId,
      status,
      summary: isReceipt
        ? 'Referral email identified'
        : workflowStep?.summary ?? pendingSummary(
            referral,
            selectedStepId,
            drkDuplicateCheckEnabled,
          ),
      occurredAt: workflowStep?.occurred_at || referral.received_at || '',
      source: 'testing-infobox' as const,
      inbox: referral,
      workflowStep,
    }})
    .filter((row) => statuses.includes(row.status))

  const demoRows = demoDays.flatMap((day) => day.rows)
  return groupRows([...demoRows, ...liveRows])
}

function pendingStepStatus(
  referral: LiveInboxReferral,
  stepId: string,
): PatientStepStatus {
  if (referral.status === 'failed') return 'blocked'
  if (referral.status === 'processing' && stepId === 'extract-and-verify') {
    return 'current'
  }
  return 'waiting'
}

function pendingSummary(
  referral: LiveInboxReferral,
  stepId: string,
  drkDuplicateCheckEnabled?: boolean,
) {
  if (referral.status === 'processing' && stepId === 'extract-and-verify') {
    return 'Extracting referral details'
  }
  if (stepId === 'check-drk' && drkDuplicateCheckEnabled === false) {
    return 'DRK chart check disabled'
  }
  return {
    'extract-and-verify': 'Queued for referral extraction',
    'check-monday': 'Queued for Monday duplicate check',
    'check-drk': 'Queued for DRK chart check',
    'confirm-referral-contacted': 'Queued for referral acknowledgement',
  }[stepId] ?? 'Queued for Stage 1 processing'
}

export function isLiveInboxRow(row: StepFeedRow): row is LiveInboxFeedRow {
  return 'source' in row && row.source === 'testing-infobox'
}

function groupRows(rows: Array<StepFeedRow | LiveInboxFeedRow>): IntakeFeedDay[] {
  const sorted = [...rows].sort(
    (a, b) => timestamp(b.occurredAt) - timestamp(a.occurredAt),
  )
  const groups = new Map<string, Array<StepFeedRow | LiveInboxFeedRow>>()
  for (const row of sorted) {
    const parsed = parseOpsDate(row.occurredAt)
    const list = groups.get(parsed.key) ?? []
    list.push(row)
    groups.set(parsed.key, list)
  }
  return [...groups.entries()].map(([key, dayRows]) => {
    const parsed = parseOpsDate(dayRows[0]?.occurredAt ?? '')
    return {
      key,
      label: parsed.label,
      month: parsed.month,
      day: parsed.day,
      rows: dayRows,
    }
  })
}

function timestamp(value: string) {
  return value ? parseOpsDate(value).timeMs : 0
}
