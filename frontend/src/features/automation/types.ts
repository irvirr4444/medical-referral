import type { FlowOpsPageId } from '../../data/flowOps'
import {
  BUTLER_INTAKE_SNAPSHOTS,
  BUTLER_CANONICAL,
} from './fixtures/butlerIntakeSnapshots'
import { patientDisplayName } from './canonicalReferral'

export type ImplementationStatus = 'working' | 'partial' | 'planned'
export type MicrostepRunStatus =
  | 'completed'
  | 'attention'
  | 'waiting'
  | 'planned'

export interface AutomationValue {
  label: string
  value: string
}

export interface ArtifactField {
  label: string
  value: string
  fieldPath?: string
  meta?: string
}

export interface ArtifactSection {
  id: string
  title: string
  fields: ArtifactField[]
  defaultExpanded?: boolean
}

export interface MicrostepExample {
  status: MicrostepRunStatus
  duration: string
  inputs: AutomationValue[]
  outputs: AutomationValue[]
  validation: string
  executionId?: string
  artifactId?: string
  referralId?: string
  patientName?: string
  executedAt?: string
  artifactTitle?: string
  knownAtThisPoint?: AutomationValue[]
  artifactSections?: ArtifactSection[]
}

export interface MicrostepExecutionSnapshot {
  executionId: string
  stepId: string
  referralId: string
  artifactId: string
  status: MicrostepRunStatus
  duration: string
  executedAt: string
  artifactTitle: string
  validation: string
  knownAtThisPoint: AutomationValue[]
  artifactSections: ArtifactSection[]
}

export interface AutomationMicrostep {
  id: string
  name: string
  description: string
  implementationStatus: ImplementationStatus
  system: string
  next: string
  example: MicrostepExample
  exceptionExample?: MicrostepExample
}

export interface AutomationStageDefinition {
  id: FlowOpsPageId
  title: string
  shortTitle: string
  purpose: string
  trigger: string
  successDefinition: string
  implementationStatus: ImplementationStatus
  microsteps: AutomationMicrostep[]
}

export type AutomationRunId =
  | 'synthetic-complete'
  | 'synthetic-exception'
  | 'butler-alva'

export interface AutomationRunFixture {
  id: AutomationRunId
  label: string
  source: string
  startedAt: string
  summary: string
  referralId?: string
  patientName?: string
  intakeSnapshots?: Record<string, MicrostepExecutionSnapshot>
}

export function snapshotToExample(
  snapshot: MicrostepExecutionSnapshot,
  patientName: string,
): MicrostepExample {
  return {
    status: snapshot.status,
    duration: snapshot.duration,
    validation: snapshot.validation,
    executionId: snapshot.executionId,
    artifactId: snapshot.artifactId,
    referralId: snapshot.referralId,
    patientName,
    executedAt: snapshot.executedAt,
    artifactTitle: snapshot.artifactTitle,
    knownAtThisPoint: snapshot.knownAtThisPoint,
    artifactSections: snapshot.artifactSections,
    inputs: snapshot.knownAtThisPoint.map((item) => ({
      label: item.label,
      value: item.value,
    })),
    outputs: [
      {
        label: snapshot.artifactTitle,
        value: snapshot.artifactSections[0]?.fields[0]?.value ?? 'Produced',
      },
    ],
  }
}

export const BUTLER_RUN_FIXTURE: AutomationRunFixture = {
  id: 'butler-alva',
  label: 'Butler, Alva — chart referral walkthrough',
  source: `Outlook email with ${BUTLER_CANONICAL.source.file_name}`,
  startedAt: 'August 10, 2026 at 9:14 AM',
  summary:
    'EHR chart export extracted into canonical form. Six of seven required fields complete; home-health agency missing; duplicate search clear; awaiting reviewer approval.',
  referralId: BUTLER_CANONICAL.referral_id,
  patientName: patientDisplayName(BUTLER_CANONICAL.patient),
  intakeSnapshots: BUTLER_INTAKE_SNAPSHOTS,
}
