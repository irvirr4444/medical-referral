import type { AutomationStageDefinition } from '../types'
import { HANDOFF_MICROSTEPS } from './handoff'
import { step } from './shared'

export const ASSIGNMENT_STAGE: AutomationStageDefinition = {
  id: 'assignment',
  title: '2. Assignment & handoff',
  shortTitle: 'Assignment & handoff',
  purpose:
    'Confirm the case manager, notify them, and prepare the approved referral in Monday.com and DRK.',
  trigger: 'Stage 1 is complete and the referral is ready to move forward.',
  successDefinition:
    'The case manager is confirmed and notified, Monday.com is verified, and the DRK form is ready for final review.',
  implementationStatus: 'partial',
  microsteps: [
    step({
      id: 'assign-owner',
      name: 'Assign Case Manager',
      description:
        'Choose and confirm the responsible case manager from the current roster.',
      system: 'WCW assignment approval',
      next: 'Notify Case Manager',
      input: 'Approved referral and case-manager roster',
      output: 'Confirmed case manager',
      validation: 'The choice is recorded once before any handoff action can run.',
      implementationStatus: 'partial',
    }),
    ...HANDOFF_MICROSTEPS,
  ],
}
