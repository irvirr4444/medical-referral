import { caseManagerSuggestion } from './caseManagerAssignments'
import { providerSuggestion } from './providerAssignments'

export interface EodSchedulingCheckRecord {
  providerName: string
  providerSelectedAt: string
  hoursSinceProviderSelected: number
  caseManagerName: string
  scheduledStatus: string
  appointmentDate: string
  scheduledComplete: string
  overdue: boolean
  escalatedToManagement?: boolean
}

export const EOD_CM_NOTIFY_HOURS = 24
export const EOD_ESCALATE_HOURS = 48

type StoredEodSchedulingCheck = Omit<
  EodSchedulingCheckRecord,
  'caseManagerName'
>

const EOD_SCHEDULING_CHECKS: Record<string, StoredEodSchedulingCheck> = {
  'maria-alvarez': {
    providerName: 'Daniel Rowady',
    providerSelectedAt: 'August 11, 2026 at 5:01 AM',
    hoursSinceProviderSelected: 36,
    scheduledStatus: 'Not Scheduled',
    appointmentDate: '',
    scheduledComplete: 'No',
    overdue: true,
  },
  'thomas-reed': {
    providerName: 'Charles Cho',
    providerSelectedAt: 'August 11, 2026 at 11:01 PM',
    hoursSinceProviderSelected: 18,
    scheduledStatus: 'Not Scheduled',
    appointmentDate: '',
    scheduledComplete: 'No',
    overdue: true,
  },
  'frank-owens': {
    providerName: 'Aaron Currie',
    providerSelectedAt: 'August 8, 2026 at 2:15 PM',
    hoursSinceProviderSelected: 51,
    scheduledStatus: 'Not Scheduled',
    appointmentDate: 'August 13, 2026',
    scheduledComplete: 'No',
    overdue: true,
  },
  'james-carter': {
    providerName: 'Daniel Rowady',
    providerSelectedAt: 'August 10, 2026 at 9:00 AM',
    hoursSinceProviderSelected: 56,
    scheduledStatus: 'Not Scheduled',
    appointmentDate: '',
    scheduledComplete: 'No',
    overdue: true,
  },
  'linda-nguyen': {
    providerName: 'Aaron Currie',
    providerSelectedAt: 'August 8, 2026 at 4:00 PM',
    hoursSinceProviderSelected: 73,
    scheduledStatus: 'Not Scheduled',
    appointmentDate: '',
    scheduledComplete: 'No',
    overdue: true,
    escalatedToManagement: true,
  },
  'george-chen': {
    providerName: 'Charles Cho',
    providerSelectedAt: 'August 9, 2026 at 11:30 AM',
    hoursSinceProviderSelected: 54,
    scheduledStatus: 'Scheduled',
    appointmentDate: 'August 14, 2026',
    scheduledComplete: 'No',
    overdue: true,
  },
  'anita-gomez': {
    providerName: 'Daniel Rowady',
    providerSelectedAt: 'August 10, 2026 at 8:00 AM',
    hoursSinceProviderSelected: 33,
    scheduledStatus: 'Scheduled',
    appointmentDate: 'August 13, 2026',
    scheduledComplete: 'Yes',
    overdue: false,
  },
  'susan-park': {
    providerName: 'Aaron Currie',
    providerSelectedAt: 'August 10, 2026 at 9:30 AM',
    hoursSinceProviderSelected: 31,
    scheduledStatus: 'Scheduled',
    appointmentDate: 'August 12, 2026',
    scheduledComplete: 'Yes',
    overdue: false,
  },
  'nancy-liu': {
    providerName: 'Aaron Currie',
    providerSelectedAt: 'August 8, 2026 at 4:30 PM',
    hoursSinceProviderSelected: 24,
    scheduledStatus: 'Scheduled',
    appointmentDate: 'August 11, 2026',
    scheduledComplete: 'Yes',
    overdue: false,
  },
  'helen-park': {
    providerName: 'Charles Cho',
    providerSelectedAt: 'August 8, 2026 at 5:00 PM',
    hoursSinceProviderSelected: 24,
    scheduledStatus: 'Scheduled',
    appointmentDate: 'August 12, 2026',
    scheduledComplete: 'Yes',
    overdue: false,
  },
}

export function eodSchedulingCheckForPatient(
  patientId: string,
): EodSchedulingCheckRecord {
  const caseManagerName = caseManagerSuggestion(patientId).name
  const record = EOD_SCHEDULING_CHECKS[patientId]
  if (record) {
    return { ...record, caseManagerName }
  }

  const provider = providerSuggestion(patientId)
  return {
    providerName: provider.name,
    providerSelectedAt: 'Not documented',
    hoursSinceProviderSelected: 0,
    caseManagerName,
    scheduledStatus: 'Not Scheduled',
    appointmentDate: '',
    scheduledComplete: 'No',
    overdue: false,
  }
}

export function eodSchedulingCheckSummary(
  record: EodSchedulingCheckRecord,
): string {
  if (record.overdue) {
    return `Not scheduled · ${record.hoursSinceProviderSelected} hours`
  }
  return 'Scheduled · Monday fields agree'
}

export function eodSchedulingCheckDisplaySummary(
  record: EodSchedulingCheckRecord,
  options?: {
    manualCmFollowUp?: boolean
    escalatedToManagement?: boolean
  },
): string {
  if (options?.escalatedToManagement) {
    return eodEscalationDue(record)
      ? 'Escalated to management'
      : 'Escalated to Nicole'
  }
  if (options?.manualCmFollowUp) {
    return `${record.caseManagerName} notified on Teams`
  }
  return eodSchedulingCheckSummary(record)
}

export function eodEscalationConfirmLabel(
  record: EodSchedulingCheckRecord,
): string {
  return eodEscalationDue(record)
    ? 'Escalated to management'
    : 'Escalated to Nicole'
}

export function eodIsUnscheduled(record: EodSchedulingCheckRecord): boolean {
  return record.overdue
}

export function eodCmAutoNotifyDue(record: EodSchedulingCheckRecord): boolean {
  return (
    record.overdue &&
    record.hoursSinceProviderSelected >= EOD_CM_NOTIFY_HOURS
  )
}

export function eodCmNotifyPending(record: EodSchedulingCheckRecord): boolean {
  return (
    record.overdue && record.hoursSinceProviderSelected < EOD_CM_NOTIFY_HOURS
  )
}

export function eodEscalationDue(record: EodSchedulingCheckRecord): boolean {
  return (
    record.overdue &&
    record.hoursSinceProviderSelected >= EOD_ESCALATE_HOURS
  )
}

export function eodFollowUpEligible(
  record: EodSchedulingCheckRecord,
  manualCmFollowUp = false,
): boolean {
  return eodCmAutoNotifyDue(record) || manualCmFollowUp
}

export function eodCmFollowUpSummary(
  record: EodSchedulingCheckRecord,
  manualFollowUp = false,
): string {
  if (manualFollowUp) {
    return `${record.caseManagerName} notified on Teams`
  }
  return `${record.caseManagerName} notified on Teams automatically`
}

export function eodCmFollowUpMessage(
  record: EodSchedulingCheckRecord,
  patientName: string,
): string {
  return `${patientName} is still not scheduled ${record.hoursSinceProviderSelected} hours after ${record.providerName} was selected. Can you confirm scheduling status and next steps?`
}

export function eodEscalationEligible(
  record: EodSchedulingCheckRecord,
  escalatedToManagement = false,
): boolean {
  return (
    record.overdue &&
    (escalatedToManagement || Boolean(record.escalatedToManagement))
  )
}

export function eodEscalationSummary(record: EodSchedulingCheckRecord): string {
  return record.escalatedToManagement
    ? 'Escalated to management · still unresolved'
    : 'Escalated to management'
}

export function eodManagementEscalationMessage(
  _record: EodSchedulingCheckRecord,
  _patientName: string,
): string {
  return 'Case manager follow-up on Teams did not resolve scheduling. Added to the management escalation email and tracking spreadsheet.'
}
