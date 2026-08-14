import type {
  PatientSchedulingRecord,
  SchedulingBlockerReason,
  SchedulingHandoffProvider,
  SchedulingHandoffRoute,
  SchedulingSlot,
} from '../../../types'
import { providerSuggestion, type ProviderOption } from './providerAssignments'

function providerOf(patientId: string): SchedulingHandoffProvider {
  const provider = providerSuggestion(patientId)
  return toHandoffProvider(provider)
}

function toHandoffProvider(provider: ProviderOption): SchedulingHandoffProvider {
  return {
    id: provider.id,
    name: provider.name,
    npi: provider.npi,
    city: provider.city,
    phone: provider.phone,
    email: provider.email,
  }
}

function slot(
  id: string,
  dateLabel: string,
  timeLabel: string,
  appointmentDate: string,
  appointmentTime: string,
  status: SchedulingSlot['status'] = 'open',
  unavailableReason?: string,
): SchedulingSlot {
  return {
    id,
    dateLabel,
    timeLabel,
    appointmentDate,
    appointmentTime,
    status,
    unavailableReason,
  }
}

export const SCHEDULING_BLOCKER_LABEL: Record<SchedulingBlockerReason, string> =
  {
    patient_declined: 'Patient declined available appointment windows',
    patient_unavailable: 'Patient unavailable for offered times',
    slots_exhausted: 'No open slots within 24–48 hours',
  }

export function schedulingBlockerLabel(reason?: SchedulingBlockerReason) {
  return reason ? SCHEDULING_BLOCKER_LABEL[reason] : 'Scheduling blocked'
}

export function openSlotCount(record: PatientSchedulingRecord) {
  return record.slots.filter((item) => item.status === 'open').length
}

export function schedulingFeedSummary(record: PatientSchedulingRecord): string {
  if (record.status === 'scheduled' && record.appointmentDate) {
    return record.appointmentTime
      ? `Scheduled · ${record.appointmentDate} at ${record.appointmentTime}`
      : `Scheduled · ${record.appointmentDate}`
  }
  if (record.status === 'blocked') {
    return schedulingBlockerLabel(record.blockerReason)
  }
  const open = openSlotCount(record)
  return open > 0
    ? `Awaiting appointment · ${open} open slot${open === 1 ? '' : 's'}`
    : SCHEDULING_BLOCKER_LABEL.slots_exhausted
}

export function selectedSlot(record: PatientSchedulingRecord) {
  return record.slots.find((item) => item.id === record.selectedSlotId) ?? null
}

function waitingRecord(input: {
  patientId: string
  patientName: string
  route?: SchedulingHandoffRoute
  syncedAt: string
  slots: SchedulingSlot[]
  selectedSlotId?: string | null
}): PatientSchedulingRecord {
  const route = input.route ?? 'provider_confirmed'
  return {
    patientId: input.patientId,
    patientName: input.patientName,
    provider: providerOf(input.patientId),
    route,
    syncedAt: input.syncedAt,
    slots: input.slots,
    selectedSlotId: input.selectedSlotId ?? null,
    status: 'waiting',
    referralSent: route === 'provider_confirmed',
  }
}

function scheduledRecord(input: {
  patientId: string
  patientName: string
  route?: SchedulingHandoffRoute
  syncedAt: string
  slots: SchedulingSlot[]
  selectedSlotId: string
  scheduledAt: string
}): PatientSchedulingRecord {
  const chosen =
    input.slots.find((item) => item.id === input.selectedSlotId) ?? input.slots[0]
  const route = input.route ?? 'provider_confirmed'
  return {
    patientId: input.patientId,
    patientName: input.patientName,
    provider: providerOf(input.patientId),
    route,
    syncedAt: input.syncedAt,
    slots: input.slots,
    selectedSlotId: chosen.id,
    status: 'scheduled',
    appointmentDate: chosen.appointmentDate,
    appointmentTime: chosen.appointmentTime,
    scheduledAt: input.scheduledAt,
    referralSent: true,
  }
}

function blockedRecord(input: {
  patientId: string
  patientName: string
  route?: SchedulingHandoffRoute
  syncedAt: string
  slots: SchedulingSlot[]
  reason: SchedulingBlockerReason
}): PatientSchedulingRecord {
  const route = input.route ?? 'provider_confirmed'
  return {
    patientId: input.patientId,
    patientName: input.patientName,
    provider: providerOf(input.patientId),
    route,
    syncedAt: input.syncedAt,
    slots: input.slots,
    selectedSlotId: null,
    status: 'blocked',
    blockerReason: input.reason,
    referralSent: route === 'provider_confirmed',
  }
}

const DEFAULT_OPEN_SLOTS: SchedulingSlot[] = [
  slot(
    'today-1530',
    'Today',
    '3:30 PM',
    'August 14, 2026',
    '3:30 PM',
  ),
  slot(
    'tomorrow-0900',
    'Tomorrow',
    '9:00 AM',
    'August 15, 2026',
    '9:00 AM',
  ),
  slot(
    'tomorrow-1330',
    'Tomorrow',
    '1:30 PM',
    'August 15, 2026',
    '1:30 PM',
  ),
  slot(
    'saturday-0840',
    'Saturday',
    '8:40 AM',
    'August 16, 2026',
    '8:40 AM',
  ),
]

export function defaultOpenSlots(patientId: string): SchedulingSlot[] {
  const prefix = patientId.slice(0, 3)
  return DEFAULT_OPEN_SLOTS.map((item) => ({
    ...item,
    id: `${prefix}-${item.id}`,
  }))
}

export function waitingScheduleFromHandoff(input: {
  patientId: string
  patientName: string
  provider: SchedulingHandoffProvider
  route: SchedulingHandoffRoute
}): PatientSchedulingRecord {
  return {
    patientId: input.patientId,
    patientName: input.patientName,
    provider: input.provider,
    route: input.route,
    syncedAt: 'Just now',
    slots: defaultOpenSlots(input.patientId),
    selectedSlotId: null,
    status: 'waiting',
    referralSent: input.route === 'provider_confirmed',
  }
}

export function upsertScheduleFromHandoff(
  schedules: Record<string, PatientSchedulingRecord>,
  input: {
    patientId: string
    patientName: string
    provider: SchedulingHandoffProvider
    route: SchedulingHandoffRoute
  },
): Record<string, PatientSchedulingRecord> {
  const existing = schedules[input.patientId]
  if (existing?.status === 'scheduled' || existing?.status === 'blocked') {
    return schedules
  }
  if (existing) {
    return {
      ...schedules,
      [input.patientId]: {
        ...existing,
        provider: input.provider,
        route: input.route,
        referralSent:
          existing.referralSent || input.route === 'provider_confirmed',
      },
    }
  }
  return {
    ...schedules,
    [input.patientId]: waitingScheduleFromHandoff(input),
  }
}

export function seedPatientSchedules(): Record<string, PatientSchedulingRecord> {
  return {
    'maria-alvarez': waitingRecord({
      patientId: 'maria-alvarez',
      patientName: 'Maria Alvarez',
      syncedAt: '2 min ago',
      slots: [
        slot('maria-today-1530', 'Today', '3:30 PM', 'August 14, 2026', '3:30 PM'),
        slot(
          'maria-tomorrow-0900',
          'Tomorrow',
          '9:00 AM',
          'August 15, 2026',
          '9:00 AM',
        ),
        slot(
          'maria-tomorrow-1330',
          'Tomorrow',
          '1:30 PM',
          'August 15, 2026',
          '1:30 PM',
          'unavailable',
          'Taken on the provider route',
        ),
        slot(
          'maria-saturday-0840',
          'Saturday',
          '8:40 AM',
          'August 16, 2026',
          '8:40 AM',
        ),
      ],
    }),
    'thomas-reed': waitingRecord({
      patientId: 'thomas-reed',
      patientName: 'Thomas Reed',
      syncedAt: '4 min ago',
      slots: [
        slot(
          'thomas-tomorrow-1015',
          'Tomorrow',
          '10:15 AM',
          'August 15, 2026',
          '10:15 AM',
        ),
        slot(
          'thomas-tomorrow-1400',
          'Tomorrow',
          '2:00 PM',
          'August 15, 2026',
          '2:00 PM',
        ),
        slot(
          'thomas-saturday-0930',
          'Saturday',
          '9:30 AM',
          'August 16, 2026',
          '9:30 AM',
        ),
      ],
    }),
    'james-carter': waitingRecord({
      patientId: 'james-carter',
      patientName: 'James Carter',
      route: 'manual_placement',
      syncedAt: '6 min ago',
      slots: [
        slot('james-today-1645', 'Today', '4:45 PM', 'August 14, 2026', '4:45 PM'),
        slot(
          'james-tomorrow-1100',
          'Tomorrow',
          '11:00 AM',
          'August 15, 2026',
          '11:00 AM',
        ),
        slot(
          'james-saturday-0815',
          'Saturday',
          '8:15 AM',
          'August 16, 2026',
          '8:15 AM',
        ),
      ],
    }),
    'linda-nguyen': blockedRecord({
      patientId: 'linda-nguyen',
      patientName: 'Linda Nguyen',
      syncedAt: 'Yesterday 5:30 PM',
      reason: 'patient_declined',
      slots: [
        slot(
          'linda-fri-1100',
          'Friday',
          '11:00 AM',
          'August 14, 2026',
          '11:00 AM',
          'unavailable',
          'Patient declined',
        ),
        slot(
          'linda-sat-0840',
          'Saturday',
          '8:40 AM',
          'August 15, 2026',
          '8:40 AM',
          'unavailable',
          'Patient declined',
        ),
      ],
    }),
    'david-ruiz': blockedRecord({
      patientId: 'david-ruiz',
      patientName: 'David Ruiz',
      syncedAt: '18 min ago',
      reason: 'slots_exhausted',
      slots: [
        slot(
          'david-mon-0900',
          'Monday',
          '9:00 AM',
          'August 17, 2026',
          '9:00 AM',
          'unavailable',
          'Outside the 24–48 hour window',
        ),
        slot(
          'david-mon-1400',
          'Monday',
          '2:00 PM',
          'August 17, 2026',
          '2:00 PM',
          'unavailable',
          'Outside the 24–48 hour window',
        ),
      ],
    }),
    'nancy-liu': scheduledRecord({
      patientId: 'nancy-liu',
      patientName: 'Nancy Liu',
      syncedAt: 'August 10, 2026 at 9:11 AM',
      selectedSlotId: 'nancy-fri-1100',
      scheduledAt: 'August 10, 2026 at 9:11 AM',
      slots: [
        slot('nancy-fri-1100', 'Friday', '11:00 AM', 'August 11, 2026', '11:00 AM'),
        slot('nancy-sat-0840', 'Saturday', '8:40 AM', 'August 12, 2026', '8:40 AM'),
      ],
    }),
    'patricia-johnson': scheduledRecord({
      patientId: 'patricia-johnson',
      patientName: 'Patricia Johnson',
      syncedAt: 'August 9, 2026 at 3:19 PM',
      selectedSlotId: 'patricia-wed-1100',
      scheduledAt: 'August 9, 2026 at 3:19 PM',
      slots: [
        slot(
          'patricia-wed-1100',
          'Wednesday',
          '11:00 AM',
          'August 13, 2026',
          '11:00 AM',
        ),
      ],
    }),
    'helen-park': scheduledRecord({
      patientId: 'helen-park',
      patientName: 'Helen Park',
      route: 'manual_placement',
      syncedAt: 'August 8, 2026 at 5:41 PM',
      selectedSlotId: 'helen-sat-0900',
      scheduledAt: 'August 8, 2026 at 5:41 PM',
      slots: [
        slot('helen-sat-0900', 'Saturday', '9:00 AM', 'August 12, 2026', '9:00 AM'),
      ],
    }),
  }
}
