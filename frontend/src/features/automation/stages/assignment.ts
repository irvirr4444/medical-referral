import type { AutomationStageDefinition } from '../types'
import { step } from './shared'

export const ASSIGNMENT_STAGE: AutomationStageDefinition = {
  id: 'assignment',
  title: '2. Assignment',
  shortTitle: 'Assignment',
  purpose: 'Confirm the case manager who will own the approved referral.',
  trigger: 'Stage 1 is complete and the referral is ready to move forward.',
  successDefinition: 'One case manager is explicitly confirmed for the referral.',
  implementationStatus: 'partial',
  microsteps: [
    step({
      id: 'determine-owner',
      name: 'Assign Case Manager',
      description: 'Choose and confirm the responsible case manager from the current roster.',
      system: 'WCW assignment approval',
      next: 'Notify Case Manager',
      input: 'Approved referral and case-manager roster',
      output: 'Confirmed case manager',
      validation: 'The choice is recorded once before any handoff action can run.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'assign-owner',
      name: 'Notify Case Manager',
      description: 'Select and record the responsible case manager or marketer.',
      system: 'WCW assignment approval',
      next: 'Begin Handoff',
      input: 'Recommended owner and routing reason',
      output: 'Verified assignment',
      validation: 'The selected owner is confirmed before referral notifications are sent.',
      implementationStatus: 'partial',
    }),
  ],
}
