import type { AutomationStageDefinition } from '../types'
import { step } from './shared'

export const ASSIGNMENT_STAGE: AutomationStageDefinition = {
  id: 'assignment',
  title: '3. Assignment',
  shortTitle: 'Assignment',
  purpose: 'Assign one responsible owner using referral completeness and service location.',
  trigger: 'The patient records are available in Monday.com and DRK.',
  successDefinition: 'The correct case manager or marketer owns the next action.',
  implementationStatus: 'planned',
  microsteps: [
    step({
      id: 'determine-owner',
      name: 'Determine Responsible Owner',
      description: 'Route complete referrals to a case manager and incomplete referrals to a marketer.',
      system: 'Assignment rules',
      next: 'Assign Owner',
      input: 'Service location, source, and missing fields',
      output: 'Recommended owner',
      validation: 'Conflicting territory matches are not auto-assigned.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'assign-owner',
      name: 'Assign Owner',
      description: 'Select and record the responsible case manager or marketer.',
      system: 'WCW approval / Monday.com / DRK',
      next: 'Begin Provider Selection',
      input: 'Recommended owner and routing reason',
      output: 'Verified assignment',
      validation: 'The selected owner is written once and verified by read-back.',
      implementationStatus: 'planned',
    }),
  ],
}
