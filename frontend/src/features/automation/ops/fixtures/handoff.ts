import type { StageOpsFixture } from '../types'
import { INTAKE_DEMO_PATIENTS } from '../../fixtures/intakeDemoPatients'
import { ev } from './event'

export const HANDOFF_OPS_FIXTURE: StageOpsFixture = {
  stageId: 'handoff',
  events: INTAKE_DEMO_PATIENTS.slice(1).flatMap((patient) => [
    ev(
      'handoff',
      'plans-loaded',
      patient.patientId,
      patient.patientName,
      patient.receivedAt,
      'Assigned case manager notified',
      'resolved',
    ),
    ev(
      'handoff',
      'monday-created',
      patient.patientId,
      patient.patientName,
      patient.receivedAt,
      'Monday.com record created from canonical referral',
      'resolved',
    ),
    ev(
      'handoff',
      'drk-prepared',
      patient.patientId,
      patient.patientName,
      patient.receivedAt,
      'DRK chart prefilled for employee review',
      'resolved',
    ),
  ]),
}
