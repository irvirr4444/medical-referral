import type { AutomationStageDefinition } from '../types'
import { step } from './shared'

export const ASSIGNMENT_STAGE: AutomationStageDefinition = {
  id: 'assignment',
  title: '2. Assignment',
  shortTitle: 'Assignment',
  purpose: 'Assign one responsible owner using referral completeness and service location.',
  trigger: 'The referral is approved and ready for assignment.',
  successDefinition: 'The correct case manager or marketer owns the next action.',
  implementationStatus: 'planned',
  microsteps: [
    step({
      id: 'determine-owner',
      name: 'Assign Case Manager',
      description: 'Route complete referrals to a case manager and incomplete referrals to a marketer.',
      system: 'Assignment rules',
      next: 'Notify Case Manager',
      input: 'Service location, source, and missing fields',
      output: 'Recommended owner',
      validation: 'Conflicting territory matches are not auto-assigned.',
      implementationStatus: 'planned',
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
      implementationStatus: 'planned',
    }),
  ],
}
