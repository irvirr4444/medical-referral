import type { StageOpsFixture } from '../types'
import { ev } from './event'
import { INTAKE_DEMO_PATIENTS } from '../../fixtures/intakeDemoPatients'

/** Intake ops fixture — Butler leads; roster is real canonical referrals. */
export const INTAKE_OPS_FIXTURE: StageOpsFixture = {
  stageId: 'intake',
  events: INTAKE_DEMO_PATIENTS.flatMap((patient) => {
    const at = patient.receivedAt
    const pdf = patient.samplePdf
    const id = patient.patientId
    const name = patient.patientName
    const fq = patient.canonical.field_quality
    const agency = fq['home_health_or_hospice']?.status
    const phone = fq['patient.phones']?.status
    const address = fq['patient.address']?.status
    const thresholdOk =
      (fq['patient.name']?.status === 'present' ||
        fq['patient.name']?.status === 'explicitly_none') &&
      (fq['patient.date_of_birth']?.status === 'present' ||
        fq['patient.date_of_birth']?.status === 'explicitly_none') &&
      (phone === 'present' || phone === 'explicitly_none') &&
      (address === 'present' || address === 'explicitly_none')
    const complete =
      agency === 'present' || agency === 'explicitly_none'

    const base = [
      ev(
        'intake',
        'emails-arrived',
        id,
        name,
        at,
        `Referral PDF received · ${pdf}`,
        'resolved',
      ),
      ev(
        'intake',
        'extracted',
        id,
        name,
        at,
        `Canonical referral extracted · ${patient.canonical.source.page_count ?? '?'} pages`,
        'resolved',
      ),
    ]

    if (!thresholdOk) {
      return [
        ...base,
        ev(
          'intake',
          'needs-information',
          id,
          name,
          at,
          'Identity/contact threshold incomplete',
          'open',
          'Waiting',
        ),
      ]
    }

    if (!complete) {
      return [
        ...base,
        ev(
          'intake',
          'needs-information',
          id,
          name,
          at,
          agency === 'unclear'
            ? 'Home-health agency unclear'
            : 'Home-health agency missing',
          'open',
          'Waiting',
        ),
        ev(
          'intake',
          'awaiting-approval',
          id,
          name,
          at,
          'Awaiting partner contact and intake confirmation',
          'open',
          'Waiting',
        ),
        ev(
          'intake',
          'destination-gated',
          id,
          name,
          at,
          'Monday and DRK writes blocked pending confirmation',
          'open',
          'Waiting',
        ),
      ]
    }

    return [
      ...base,
      ev(
        'intake',
        'approved-rejected',
        id,
        name,
        at,
        'Approved by reviewer',
        'resolved',
      ),
      ev(
        'intake',
        'destination-gated',
        id,
        name,
        at,
        'Destination preparation authorized',
        'resolved',
      ),
    ]
  }),
}
