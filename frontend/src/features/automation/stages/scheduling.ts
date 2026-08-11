import type { AutomationStageDefinition } from '../types'
import { step } from './shared'

export const SCHEDULING_STAGE: AutomationStageDefinition = {
  id: 'scheduling',
  title: '5. Scheduling',
  shortTitle: 'Scheduling',
  purpose:
    'Coordinate and confirm an appointment within the targeted 24-48-hour window, then record it across WCW systems.',
  trigger: 'A WCW employee confirms the provider selected for the referral.',
  successDefinition:
    'The appointment is confirmed and reconciled across approved systems, or its blocker is explicit.',
  implementationStatus: 'planned',
  microsteps: [
    step({
      id: 'load-scheduling-context',
      name: 'Load patient and provider details',
      description:
        'Collect patient availability, location, provider, and current appointment state.',
      system: 'Workflow database',
      next: 'Send the referral to the provider',
      input: 'Confirmed provider and patient contact information',
      output: 'Scheduling context',
      validation: 'The system never assumes patient availability.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'read-availability',
      name: 'Send the referral to the selected provider',
      description:
        'Send the approved referral and record that the provider received it.',
      system: 'Referral delivery',
      next: 'Monitor the provider response',
      input: 'Approved referral and selected provider',
      output: 'Referral sent with delivery record',
      validation: 'The patient and provider match the approved selection.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'generate-windows',
      name: 'Monitor the provider response',
      description:
        'Track whether the selected provider responds within the one-hour window.',
      system: 'Response monitor',
      next: 'Read provider availability',
      input: 'Referral delivery record and one-hour deadline',
      output: 'Provider confirmed, declined, or timed out',
      validation: 'Only a response tied to this referral is accepted.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'present-windows',
      name: 'Read provider availability',
      description:
        'Read the confirmed provider availability and current route information.',
      system: 'Schedule adapter',
      next: 'Generate appointment options',
      input: 'Confirmed provider and service area',
      output: 'Current provider availability',
      validation: 'Stale or incomplete availability is rejected.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'monitor-response',
      name: 'Generate appointment options',
      description:
        'Combine availability, travel constraints, and WCW scheduling rules.',
      system: 'Scheduling rules',
      next: 'Confirm the appointment',
      input: 'Provider availability and route context',
      output: 'Ranked appointment options',
      validation: 'Every option includes its source and assumptions.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'classify-response',
      name: 'Confirm the appointment',
      description:
        'Let the responsible WCW employee confirm an appointment or flag a blocker.',
      system: 'Human confirmation',
      next: 'Record the appointment',
      input: 'Ranked appointment options',
      output: 'Confirmed appointment or scheduling blocker',
      validation: 'No appointment is recorded without human confirmation.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'write-appointment',
      name: 'Record the appointment in Monday.com and DRK',
      description:
        'Apply the authorized date and time to the approved systems.',
      system: 'DRK / Monday adapters',
      next: 'Reconcile appointment state',
      input: 'Human-confirmed appointment',
      output: 'Destination write receipts',
      validation:
        'Writes are idempotent and tied to the proposal that was confirmed.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'reconcile-appointment',
      name: 'Verify that scheduling is complete',
      description:
        'Read back appointment state and close or escalate the scheduling workflow.',
      system: 'Reconciliation worker',
      next: 'Enter End-of-day monitoring',
      input: 'Expected appointment and write receipts',
      output: 'Verified scheduled state or unresolved exception',
      validation:
        'The workflow closes only when expected and observed state agree.',
      implementationStatus: 'planned',
    }),
  ],
}
