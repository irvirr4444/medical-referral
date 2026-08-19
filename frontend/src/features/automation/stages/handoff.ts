import type { AutomationStageDefinition } from '../types'
import { step } from './shared'

export const HANDOFF_MICROSTEPS = [
  step({
    id: 'notify-referral-source',
    name: 'Notify Case Manager',
    description:
      'Send the approved referral and PDF to the confirmed case manager.',
    system: 'Outlook',
    next: 'Create Monday.com Record',
    input: 'Approved referral, assigned case manager, and PDF',
    output: 'Case-manager notification delivered',
    validation: 'The message identifies the correct patient and assigned case manager.',
  }),
  step({
    id: 'create-monday-record',
    name: 'Create Monday.com Record',
    description: 'Write the approved referral into the Master Sheet.',
    system: 'Monday.com',
    next: 'Prepare DRK Chart',
    input: 'Approved patient fields',
    output: 'Master Sheet item',
    validation: 'A repeated request cannot create a duplicate item.',
  }),
  step({
    id: 'create-update-drk',
    name: 'Prepare DRK Chart',
    description:
      'Open and prefill the DRK chart while leaving final creation to the employee.',
    system: 'DRK',
    next: 'Begin Provider Selection',
    input: 'Approved referral and duplicate result',
    output: 'Prefilled DRK form awaiting final review',
    validation:
      'Unresolved identity matches block prefill and the automation never presses Create.',
    implementationStatus: 'partial',
  }),
]

/** Legacy Stage 3 definition kept for fixture and lookup compatibility. */
export const HANDOFF_STAGE: AutomationStageDefinition = {
  id: 'handoff',
  title: '2. Assignment & handoff',
  shortTitle: 'Assignment & handoff',
  purpose:
    'Confirm the case manager, notify them, and prepare the approved referral in Monday.com and DRK.',
  trigger: 'Stage 1 is complete and the referral is ready to move forward.',
  successDefinition:
    'The case manager is confirmed and notified, Monday.com is verified, and the DRK form is ready for final review.',
  implementationStatus: 'partial',
  microsteps: HANDOFF_MICROSTEPS,
}
