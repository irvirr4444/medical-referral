import type { AutomationStageDefinition } from '../types'
import { step } from './shared'

export const SCHEDULING_STAGE: AutomationStageDefinition = {
  id: 'scheduling',
  title: '5. Scheduling',
  shortTitle: 'Scheduling',
  purpose:
    'Send the referral to the confirmed provider and schedule the patient within 24–48 hours.',
  trigger:
    'A provider is selected and availability is confirmed or placed by the case manager.',
  successDefinition:
    'The patient has an appointment date, or the scheduling blocker is explicit.',
  implementationStatus: 'partial',
  microsteps: [
    step({
      id: 'send-referral-provider',
      name: 'Send Referral to Provider',
      description:
        'Send the patient referral and clinical documents after provider availability is confirmed.',
      system: 'Secure referral delivery / Monday.com',
      next: 'Schedule Patient',
      input: 'Confirmed provider and approved referral packet',
      output: 'Delivery receipt and Referral sent to provider status',
      validation: 'The full referral is never sent before the provider selection is confirmed.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'schedule-patient',
      name: 'Schedule Patient',
      description:
        'Place the patient within 24–48 hours using the confirmed provider availability.',
      system: 'Case manager / routing and scheduling',
      next: 'Enter End-of-day monitoring',
      input: 'Provider availability and patient scheduling constraints',
      output: 'Confirmed appointment date and time',
      validation: 'The selected appointment must come from current provider availability.',
      implementationStatus: 'working',
    }),
  ],
}
