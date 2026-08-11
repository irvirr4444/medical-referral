import type { AutomationStageDefinition } from '../types'
import { step } from './shared'

export const WEEKLY_STAGE: AutomationStageDefinition = {
  id: 'weekly',
  title: '7. Weekly visit cycle',
  shortTitle: 'Weekly visit cycle',
  purpose:
    'Track weekly visits, missed appointments, holds, healing, expiration, and conditions requiring discharge review.',
  trigger:
    'The weekly monitor runs for active linked patients with expected visit activity.',
  successDefinition:
    'Every recorded visit outcome leads to the correct follow-up, hold tracking, or human review.',
  implementationStatus: 'partial',
  microsteps: [
    step({
      id: 'start-weekly-cycle',
      name: 'Load the weekly patient schedule',
      description:
        'Confirm source health and load active patients due for this weekly review.',
      system: 'Monitoring worker',
      next: 'Check the DRK progress note',
      input: 'Worker configuration and last successful cursor',
      output: 'Patients due for weekly visit review',
      validation: 'A failed source cannot be interpreted as no visit.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'read-visit-status',
      name: 'Check the DRK progress note',
      description:
        'Collect Monday and DRK values for visit outcome, hold, healing, expiration, and discharge.',
      system: 'Monday and DRK readers',
      next: 'Record Seen or Not Seen',
      input: 'Linked Monday item and DRK chart IDs',
      output: 'Timestamped visit-status snapshots',
      validation: 'Raw source values retain their source and observation time.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'normalize-visit-status',
      name: 'Record Seen or Not Seen',
      description:
        'Translate the recorded visit result into the status used by the WCW workflow.',
      system: 'Visit status service',
      next: 'Check healing, expiration, and hold status',
      input: 'Source-specific visit values',
      output:
        'Seen, not seen, hold, returned, healed, expired, discharged, or indeterminate',
      validation: 'Unknown values remain indeterminate.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'detect-visit-change',
      name: 'Check healing, expiration, and hold status',
      description:
        'Check whether the patient healed, expired, entered a hold, or is ready to return.',
      system: 'Visit status service',
      next: 'Update the consecutive Not Seen count',
      input: 'Recorded visit, patient status, and previous state',
      output: 'Continue care, hold action, QA review, or discharge-review condition',
      validation: 'Clinical and discharge decisions always remain human-controlled.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'update-not-seen-counter',
      name: 'Update the consecutive Not Seen count',
      description:
        'Increment on explicit not-seen events and reset after an explicit seen event.',
      system: 'Visit policy',
      next: 'Route cases needing human review',
      input: 'Meaningful seen or not-seen event',
      output: 'Updated consecutive-not-seen count',
      validation: 'Missing or indeterminate data never increments the count.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'classify-weekly-review',
      name: 'Route cases needing human review',
      description:
        'Create review work for third not-seen, healed, expired, hold, or discharge-related changes.',
      system: 'Visit policy',
      next: 'Prepare the responsible team action',
      input: 'Normalized event and counters',
      output: 'No action, management review, QA review, or hold tracking',
      validation: 'The automation never discharges a patient automatically.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'create-weekly-exception',
      name: 'Prepare the responsible team action',
      description:
        'Prepare the rescheduling, hold, QA, or discharge-review task with its supporting evidence.',
      system: 'Workflow task service',
      next: 'Update systems and notify the team',
      input: 'Review classification and source evidence',
      output: 'One clear action assigned to the responsible team',
      validation:
        'Existing unresolved exceptions are updated rather than duplicated.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'notify-and-reconcile',
      name: 'Update WCW systems and notify the team',
      description:
        'Send the review summary, then resolve it only after a later explicit source update.',
      system: 'Notification and monitoring workers',
      next: 'Continue the next weekly cycle',
      input: 'Open exception and configured recipients',
      output: 'Delivery receipt and eventual resolution event',
      validation:
        'Human approval remains required for clinical and discharge actions.',
      implementationStatus: 'partial',
    }),
  ],
}
