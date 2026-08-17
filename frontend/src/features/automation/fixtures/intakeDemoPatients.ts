import type { CanonicalReferral } from '../canonicalReferral'
import { patientDisplayName } from '../canonicalReferral'
import { buildIntakeSnapshots } from './butlerIntakeSnapshots'
import butlerCanonical from './butlerCanonicalReferral.json'
import zadranCanonical from './canonicals/zadran-khojagul.json'
import eliutCanonical from './canonicals/eliut-cruz-pagan.json'
import fayCanonical from './canonicals/fay-william.json'
import rodriguezCanonical from './canonicals/rodriguez-anita.json'
import sardinaCanonical from './canonicals/sardina-frank.json'
import gonzalezCanonical from './canonicals/gonzalez-eric.json'
import type { MicrostepExecutionSnapshot } from '../types'

export type IntakeDemoPatient = {
  patientId: string
  patientName: string
  samplePdf: string
  receivedAt: string
  canonical: CanonicalReferral
  snapshots: Record<string, MicrostepExecutionSnapshot>
}

function demoPatient(
  patientId: string,
  canonical: CanonicalReferral,
  receivedAt: string,
): IntakeDemoPatient {
  const record = canonical
  return {
    patientId,
    patientName: patientDisplayName(record.patient),
    samplePdf: record.source.file_name,
    receivedAt,
    canonical: record,
    snapshots: buildIntakeSnapshots(record, {
      runPrefix: patientId,
      executedAt: receivedAt,
    }),
  }
}

/** Referral intake demo roster: Butler + six real canonical referrals. */
export const INTAKE_DEMO_PATIENTS: IntakeDemoPatient[] = [
  demoPatient(
    'butler-alva',
    butlerCanonical as unknown as CanonicalReferral,
    'August 10, 2026 at 9:14 AM',
  ),
  demoPatient(
    'gonzalez-eric',
    gonzalezCanonical as unknown as CanonicalReferral,
    'August 10, 2026 at 11:05 AM',
  ),
  demoPatient(
    'rodriguez-anita',
    rodriguezCanonical as unknown as CanonicalReferral,
    'August 10, 2026 at 10:22 AM',
  ),
  demoPatient(
    'sardina-frank',
    sardinaCanonical as unknown as CanonicalReferral,
    'August 10, 2026 at 8:40 AM',
  ),
  demoPatient(
    'fay-william',
    fayCanonical as unknown as CanonicalReferral,
    'August 9, 2026 at 3:18 PM',
  ),
  demoPatient(
    'eliut-cruz-pagan',
    eliutCanonical as unknown as CanonicalReferral,
    'August 9, 2026 at 1:05 PM',
  ),
  demoPatient(
    'zadran-khojagul',
    zadranCanonical as unknown as CanonicalReferral,
    'August 8, 2026 at 4:42 PM',
  ),
]

export const INTAKE_DEMO_BY_ID: Record<string, IntakeDemoPatient> =
  Object.fromEntries(
    INTAKE_DEMO_PATIENTS.map((patient) => [patient.patientId, patient]),
  )

export function intakeDemoPatient(patientId: string) {
  return INTAKE_DEMO_BY_ID[patientId]
}

const PATIENT_REFERRAL_PDFS: Record<string, string> = {
  'thomas-reed': 'EC - REFERRAL FORM.pdf',
  'patricia-johnson': 'BUTLER, ALVA demo.pdf',
  'maria-alvarez': 'fax20260713-16377-syrmla.pdf',
  'helen-park': 'fax20260711-48483-ougwp2.pdf',
  'nancy-liu': 'fax20260710-1422744-nkqbp2.pdf',
  'irene-cho': 'fax20260713-2485963-94q8kc.pdf',
  'betty-hayes': 'fax20260713-620-tw3x6v.pdf',
  'james-carter': 'fax20260713-2485963-94q8kc.pdf',
  'linda-nguyen': 'fax20260713-620-tw3x6v.pdf',
}

export function referralPdfForPatient(patientId: string): string {
  return (
    INTAKE_DEMO_BY_ID[patientId]?.samplePdf ??
    PATIENT_REFERRAL_PDFS[patientId] ??
    'BUTLER, ALVA demo.pdf'
  )
}
