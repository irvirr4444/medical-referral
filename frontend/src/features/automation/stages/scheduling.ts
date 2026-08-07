import type { AutomationStageDefinition } from '../types'
import { step } from './shared'

export const SCHEDULING_STAGE: AutomationStageDefinition = {
  id: 'scheduling',
  title: '5. Scheduling',
  shortTitle: 'Scheduling',
  purpose:
    'Coordinate a confirmed appointment from approved provider availability and route constraints.',
  trigger: 'A WCW employee confirms the provider selected for the referral.',
  successDefinition:
    'The appointment is confirmed and reconciled across approved systems, or its blocker is explicit.',
  implementationStatus: 'planned',
  microsteps: [
    step({
      id: 'load-scheduling-context',
      name: 'Load scheduling context',
      description:
        'Collect patient availability, location, provider, and current appointment state.',
      system: 'Workflow database',
      next: 'Read provider availability',
      input: 'Confirmed provider and patient contact information',
      output: 'Scheduling context',
      validation: 'The system never assumes patient availability.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'read-availability',
      name: 'Read provider availability',
      description:
        'Obtain approved availability and route information from the confirmed source.',
      system: 'Schedule adapter',
      next: 'Generate candidate windows',
      input: 'Provider and service area',
      output: 'Current availability windows',
      validation: 'Stale availability is rejected.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'generate-windows',
      name: 'Generate route-aware windows',
      description:
        'Combine availability, travel constraints, and WCW scheduling rules.',
      system: 'Scheduling rules',
      next: 'Present windows for confirmation',
      input: 'Availability and route context',
      output: 'Ranked candidate appointment windows',
      validation: 'Every proposed window includes its source and assumptions.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'present-windows',
      name: 'Present windows for human confirmation',
      description:
        'Show the candidate windows to the responsible employee or approved recipient.',
      system: 'Human scheduling surface',
      next: 'Monitor the response window',
      input: 'Ranked appointment windows',
      output: 'Proposal sent with correlation identifier',
      validation: 'No appointment is recorded before explicit confirmation.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'monitor-response',
      name: 'Monitor the response window',
      description:
        'Track whether the provider or responsible person responds within the configured period.',
      system: 'Scheduling monitor',
      next: 'Classify the response',
      input: 'Proposal and configured one-hour deadline',
      output: 'Confirmed, declined, or timed-out response',
      validation: 'Only a correlated response can satisfy the proposal.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'classify-response',
      name: 'Classify scheduling outcome',
      description:
        'Determine whether to confirm, propose another window, or escalate.',
      system: 'Scheduling policy',
      next: 'Write the appointment or exception',
      input: 'Correlated response',
      output: 'Confirmed appointment or scheduling exception',
      validation: 'Ambiguous responses are routed for human clarification.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'write-appointment',
      name: 'Write the confirmed appointment',
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
      name: 'Verify the appointment',
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
