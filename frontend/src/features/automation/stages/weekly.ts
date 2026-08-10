import type { AutomationStageDefinition } from '../types'
import { step } from './shared'

export const WEEKLY_STAGE: AutomationStageDefinition = {
  id: 'weekly',
  title: '7. Weekly visit cycle',
  shortTitle: 'Weekly visit cycle',
  purpose:
    'Track weekly visit outcomes, reschedule missed visits, manage holds, and route healing, expiration, or repeated noncompliance for discharge review.',
  trigger:
    'The weekly monitor runs for active linked patients with expected visit activity.',
  successDefinition:
    'Meaningful status changes produce deduplicated events and the correct human review exception.',
  implementationStatus: 'partial',
  microsteps: [
    step({
      id: 'start-weekly-cycle',
      name: 'Start the weekly cycle',
      description:
        'Confirm source health and define the patient window for this monitoring run.',
      system: 'Monitoring worker',
      next: 'Load active patient links',
      input: 'Worker configuration and last successful cursor',
      output: 'One bounded weekly cycle',
      validation: 'A failed source cannot be interpreted as no visit.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'load-active-links',
      name: 'Load active patient links',
      description:
        'Select only patients with internal, Monday, and DRK identities needed for monitoring.',
      system: 'Workflow database',
      next: 'Read visit status',
      input: 'Active patient links and due window',
      output: 'Bounded linked-patient set',
      validation:
        'The live reader never searches all patients indiscriminately.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'read-visit-status',
      name: 'Read recorded visit status',
      description:
        'Collect Monday and DRK values for visit outcome, hold, healing, expiration, and discharge.',
      system: 'Monday and DRK readers',
      next: 'Normalize the status',
      input: 'Linked Monday item and DRK chart IDs',
      output: 'Timestamped visit-status snapshots',
      validation: 'Raw source values retain their source and observation time.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'normalize-visit-status',
      name: 'Normalize visit status',
      description:
        'Map explicit source values into the supported workflow vocabulary.',
      system: 'Visit normalizer',
      next: 'Compare with the previous snapshot',
      input: 'Source-specific visit values',
      output:
        'Seen, not seen, hold, returned, healed, expired, discharged, or indeterminate',
      validation: 'Unknown values remain indeterminate.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'detect-visit-change',
      name: 'Detect meaningful changes',
      description:
        'Compare current and previous normalized snapshots to avoid duplicate events.',
      system: 'Workflow observer',
      next: 'Update the not-seen counter',
      input: 'Current and previous normalized snapshots',
      output: 'New event or no meaningful change',
      validation: 'Repeated identical polls do not create new workflow events.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'update-not-seen-counter',
      name: 'Update consecutive not-seen count',
      description:
        'Increment on explicit not-seen events and reset after an explicit seen event.',
      system: 'Visit policy',
      next: 'Classify review requirements',
      input: 'Meaningful seen or not-seen event',
      output: 'Updated consecutive-not-seen count',
      validation: 'Missing or indeterminate data never increments the count.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'classify-weekly-review',
      name: 'Classify human review requirements',
      description:
        'Create review work for third not-seen, healed, expired, hold, or discharge-related changes.',
      system: 'Visit policy',
      next: 'Create a deduplicated exception',
      input: 'Normalized event and counters',
      output: 'No action, management review, QA review, or hold tracking',
      validation: 'The automation never discharges a patient automatically.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'create-weekly-exception',
      name: 'Create a deduplicated exception',
      description:
        'Persist the review reason, evidence, patient link, and responsible recipient.',
      system: 'Workflow exception store',
      next: 'Notify the responsible team',
      input: 'Review classification and source evidence',
      output: 'One open exception with a stable deduplication key',
      validation:
        'Existing unresolved exceptions are updated rather than duplicated.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'notify-and-reconcile',
      name: 'Notify and reconcile',
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
