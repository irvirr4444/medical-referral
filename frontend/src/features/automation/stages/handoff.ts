import type { AutomationStageDefinition } from '../types'
import { step } from './shared'

export const HANDOFF_STAGE: AutomationStageDefinition = {
  id: 'handoff',
  title: '3. Handoff',
  shortTitle: 'Handoff',
  purpose: 'Notify the referral source and assigned case manager, then create and verify the patient records.',
  trigger: 'The referral is approved and a responsible case manager or marketer is assigned.',
  successDefinition: 'Monday.com and DRK contain verified records for the same referral.',
  implementationStatus: 'partial',
  microsteps: [
    step({
      id: 'notify-referral-source',
      name: 'Notify referral source',
      description: 'Acknowledge the referral source and send the referral PDF to the assigned case manager.',
      system: 'Outlook',
      next: 'Create Monday.com Record',
      input: 'Approved referral, source contact, assigned case manager, and PDF',
      output: 'Acknowledgment delivered and case manager notified',
      validation: 'The message identifies the correct patient, referral source, and assigned case manager.',
    }),
    step({
      id: 'create-monday-record',
      name: 'Create Monday.com Record',
      description: 'Write the approved referral into the Master Sheet.',
      system: 'Monday.com',
      next: 'Create DRK Chart',
      input: 'Approved patient fields',
      output: 'Master Sheet item',
      validation: 'A repeated request cannot create a duplicate item.',
    }),
    step({
      id: 'create-update-drk',
      name: 'Create DRK Chart',
      description: 'Create the chart or update the confirmed patient match.',
      system: 'DRK',
      next: 'Begin Provider Selection',
      input: 'Approved referral and duplicate result',
      output: 'DRK chart',
      validation: 'Unresolved identity matches block the write.',
      implementationStatus: 'planned',
    }),
  ],
}
