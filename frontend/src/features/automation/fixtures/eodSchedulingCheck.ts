import { caseManagerSuggestion } from './caseManagerAssignments'
import { providerSuggestion } from './providerAssignments'
import type { PatientSchedulingRecord } from '../../../types'

export interface EodSchedulingCheckRecord {
  providerName: string
  providerSelectedAt: string
  hoursSinceProviderSelected: number
  caseManagerName: string
  scheduledStatus: string
  appointmentDate: string
  scheduledComplete: string
  overdue: boolean
  cmFollowUpSent?: boolean
  escalatedToManagement?: boolean
}

export const EOD_CM_NOTIFY_HOURS = 24
export const EOD_ESCALATE_HOURS = 48

// Case manager comes from the assignment fixture at read time, so the seeds
// below intentionally leave it out.
const EOD_SCHEDULING_CHECKS: Record<
  string,
  Omit<EodSchedulingCheckRecord, 'caseManagerName'>
> = {
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
  'marcus-feldman': {
    providerName: 'Daniel Rowady',
    providerSelectedAt: 'August 11, 2026 at 1:00 PM',
    hoursSinceProviderSelected: 28,
    scheduledStatus: 'Not Scheduled',
    appointmentDate: '',
    scheduledComplete: 'No',
    overdue: true,
  },
  'david-ruiz': {
    providerName: 'Aaron Currie',
    providerSelectedAt: 'August 10, 2026 at 4:00 PM',
    hoursSinceProviderSelected: 41,
    scheduledStatus: 'Not Scheduled',
    appointmentDate: '',
    scheduledComplete: 'No',
    overdue: true,
  },
  'patricia-johnson': {
    providerName: 'Aaron Currie',
    providerSelectedAt: 'August 10, 2026 at 2:00 PM',
    hoursSinceProviderSelected: 40,
    scheduledStatus: 'Scheduled',
    appointmentDate: 'August 13, 2026',
    scheduledComplete: 'Yes',
    overdue: false,
    cmFollowUpSent: true,
  },
  'irene-cho': {
    providerName: 'Daniel Rowady',
    providerSelectedAt: 'August 11, 2026 at 9:00 AM',
    hoursSinceProviderSelected: 32,
    scheduledStatus: 'Scheduled',
    appointmentDate: 'August 12, 2026',
    scheduledComplete: 'Yes',
    overdue: false,
    cmFollowUpSent: true,
  },
  'betty-hayes': {
    providerName: 'Charles Cho',
    providerSelectedAt: 'August 9, 2026 at 8:00 AM',
    hoursSinceProviderSelected: 62,
    scheduledStatus: 'Not Scheduled',
    appointmentDate: '',
    scheduledComplete: 'No',
    overdue: true,
    escalatedToManagement: true,
  },
  'walter-grant': {
    providerName: 'Aaron Currie',
    providerSelectedAt: 'August 8, 2026 at 10:00 AM',
    hoursSinceProviderSelected: 80,
    scheduledStatus: 'Not Scheduled',
    appointmentDate: 'August 14, 2026',
    scheduledComplete: 'No',
    overdue: true,
    escalatedToManagement: true,
  },
  'arthur-kim': {
    providerName: 'Daniel Rowady',
    providerSelectedAt: 'August 9, 2026 at 3:00 PM',
    hoursSinceProviderSelected: 52,
    scheduledStatus: 'Scheduled',
    appointmentDate: 'August 13, 2026',
    scheduledComplete: 'Yes',
    overdue: false,
    cmFollowUpSent: true,
    escalatedToManagement: true,
  },
  'gloria-bennett': {
    providerName: 'Charles Cho',
    providerSelectedAt: 'August 9, 2026 at 6:00 PM',
    hoursSinceProviderSelected: 58,
    scheduledStatus: 'Not Scheduled',
    appointmentDate: '',
    scheduledComplete: 'No',
    overdue: true,
    escalatedToManagement: true,
  },
  'dorothy-lane': {
    providerName: 'Aaron Currie',
    providerSelectedAt: 'August 9, 2026 at 1:00 PM',
    hoursSinceProviderSelected: 67,
    scheduledStatus: 'Not Scheduled',
    appointmentDate: 'August 15, 2026',
    scheduledComplete: 'No',
    overdue: true,
    escalatedToManagement: true,
  },
  'margaret-ellis': {
    providerName: 'Daniel Rowady',
    providerSelectedAt: 'August 8, 2026 at 7:00 PM',
    hoursSinceProviderSelected: 71,
    scheduledStatus: 'Not Scheduled',
    appointmentDate: '',
    scheduledComplete: 'No',
    overdue: true,
    escalatedToManagement: true,
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

export function applyLiveScheduleToEod(
  record: EodSchedulingCheckRecord,
  schedule?: PatientSchedulingRecord | null,
): EodSchedulingCheckRecord {
  if (!schedule) return record
  if (schedule.status === 'scheduled' && schedule.appointmentDate) {
    return {
      ...record,
      providerName: schedule.provider.name,
      scheduledStatus: 'Scheduled',
      appointmentDate: schedule.appointmentDate,
      scheduledComplete: 'Yes',
      overdue: false,
    }
  }
  if (schedule.status === 'blocked') {
    return {
      ...record,
      providerName: schedule.provider.name,
      scheduledStatus: 'Not Scheduled',
      appointmentDate: '',
      scheduledComplete: 'No',
      overdue: true,
    }
  }
  return {
    ...record,
    providerName: schedule.provider.name,
  }
}

export function eodSchedulingCheckForPatient(
  patientId: string,
  liveSchedule?: PatientSchedulingRecord | null,
): EodSchedulingCheckRecord {
  const caseManagerName = caseManagerSuggestion(patientId).name
  const record = EOD_SCHEDULING_CHECKS[patientId]
  const base = record
    ? { ...record, caseManagerName }
    : {
        providerName: providerSuggestion(patientId).name,
        providerSelectedAt: 'Not documented',
        hoursSinceProviderSelected: 0,
        caseManagerName,
        scheduledStatus: 'Not Scheduled',
        appointmentDate: '',
        scheduledComplete: 'No',
        overdue: false,
      }
  return applyLiveScheduleToEod(base, liveSchedule)
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

export type EodSchedulingBucket =
  | 'scheduled'
  | 'unscheduled-over-48'
  | 'unscheduled-under-48'

export function eodSchedulingBucket(
  record: EodSchedulingCheckRecord,
): EodSchedulingBucket {
  if (record.scheduledStatus === 'Scheduled' && !record.overdue) {
    return 'scheduled'
  }
  if (record.hoursSinceProviderSelected >= EOD_ESCALATE_HOURS) {
    return 'unscheduled-over-48'
  }
  return 'unscheduled-under-48'
}

export function eodSchedulingStatusLabel(
  record: EodSchedulingCheckRecord,
): string {
  switch (eodSchedulingBucket(record)) {
    case 'scheduled':
      return 'Scheduled'
    case 'unscheduled-over-48':
      return 'Not scheduled after 48h'
    case 'unscheduled-under-48':
      return 'Not scheduled less than 48h'
  }
}

export function eodSchedulingHoursMeta(
  record: EodSchedulingCheckRecord,
): string {
  const hours = `${record.hoursSinceProviderSelected} hours · provider selected ${record.providerSelectedAt}`
  if (record.appointmentDate) {
    return `${hours} · appointment ${record.appointmentDate}`
  }
  return hours
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
  return (
    manualCmFollowUp ||
    Boolean(record.cmFollowUpSent) ||
    eodCmAutoNotifyDue(record)
  )
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
  if (eodSchedulingBucket(record) === 'scheduled') {
    const when = record.appointmentDate ? ` for ${record.appointmentDate}` : ''
    return `${patientName} is now scheduled${when} with ${record.providerName}. Case manager confirmed after the Teams follow-up.`
  }
  return `${patientName} is still not scheduled ${record.hoursSinceProviderSelected} hours after ${record.providerName} was selected. Can you confirm scheduling status and next steps?`
}

export function eodEscalationEligible(
  record: EodSchedulingCheckRecord,
  escalatedToManagement = false,
): boolean {
  return escalatedToManagement || Boolean(record.escalatedToManagement)
}

export function eodEscalationSummary(record: EodSchedulingCheckRecord): string {
  if (eodSchedulingBucket(record) === 'scheduled') {
    return 'Escalated to management · now scheduled'
  }
  return record.escalatedToManagement
    ? 'Escalated to management · still unresolved'
    : 'Escalated to management'
}

export function eodManagementEscalationMessage(
  record: EodSchedulingCheckRecord,
  patientName: string,
): string {
  if (eodSchedulingBucket(record) === 'scheduled') {
    const when = record.appointmentDate
      ? ` Appointment is ${record.appointmentDate}.`
      : ''
    return `${patientName} was escalated after Teams follow-up.${when} Close out on the management tracking spreadsheet.`
  }
  return `${patientName} is still not scheduled ${record.hoursSinceProviderSelected} hours after ${record.providerName} was selected. Case manager follow-up on Teams did not resolve scheduling. Added to the management escalation email and tracking spreadsheet.`
}
