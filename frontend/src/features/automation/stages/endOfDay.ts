import type { AutomationStageDefinition } from '../types'
import { step } from './shared'

export const END_OF_DAY_STAGE: AutomationStageDefinition = {
  id: 'end-of-day',
  title: '6. End-of-day check',
  shortTitle: 'End-of-day check',
  purpose:
    "Find referrals that should be scheduled but remain unresolved after WCW's configured cutoff.",
  trigger:
    "The monitoring worker reaches the approved end-of-day cutoff in WCW's timezone.",
  successDefinition:
    'Each due referral is scheduled, explicitly indeterminate, or represented once in an actionable exception list.',
  implementationStatus: 'partial',
  microsteps: [
    step({
      id: 'start-eod-cycle',
      name: 'Start the end-of-day cycle',
      description:
        'Confirm the configured timezone, cutoff, and monitor health before evaluating patients.',
      system: 'Monitoring worker',
      next: 'Load due referrals',
      input: 'WCW cutoff configuration and worker heartbeat',
      output: 'One dated monitoring cycle',
      validation:
        'A stale or unhealthy source blocks conclusions and raises a monitoring alert.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'load-due-referrals',
      name: 'Load referrals due for scheduling',
      description:
        'Select active referrals expected to have an appointment by the cutoff.',
      system: 'Workflow database',
      next: 'Read Monday and DRK status',
      input: 'Active linked referrals and due-date rules',
      output: 'Bounded list of due referrals',
      validation:
        'Completed, discharged, and future-due referrals are excluded.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'read-eod-sources',
      name: 'Read Monday and DRK state',
      description:
        'Collect the latest recorded scheduling fields from each available source.',
      system: 'Monday and DRK readers',
      next: 'Normalize scheduling state',
      input: 'Monday item and DRK chart identifiers',
      output: 'Timestamped source snapshots',
      validation:
        'Source failures remain distinct from an unscheduled patient.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'normalize-scheduling',
      name: 'Normalize scheduling state',
      description:
        'Convert source-specific fields into scheduled, unscheduled, or indeterminate.',
      system: 'Monitoring normalizer',
      next: 'Check existing notifications',
      input: 'Monday and DRK snapshots',
      output: 'Normalized scheduling classification',
      validation: 'Only explicit recorded values can produce scheduled status.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'dedupe-eod-alerts',
      name: 'Check existing notifications',
      description:
        'Avoid repeating alerts already covered by an existing exception or Monday recipe.',
      system: 'Exception store',
      next: 'Create or update exceptions',
      input: 'Classification, patient, owner, and monitoring date',
      output: 'New, existing, or already-covered exception key',
      validation:
        'The deduplication key is stable per patient and scheduling day.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'create-eod-exceptions',
      name: 'Create actionable exceptions',
      description:
        'Record the patient, owner, provider, appointment state, and blocker.',
      system: 'Workflow exception store',
      next: 'Send the consolidated summary',
      input: 'Unscheduled and indeterminate classifications',
      output: 'One open exception per affected patient',
      validation: 'Exceptions never make scheduling decisions.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'notify-eod',
      name: 'Send the consolidated summary',
      description:
        'Email one management list rather than multiple duplicate patient alerts.',
      system: 'Notification outbox',
      next: 'Recheck unresolved exceptions',
      input: 'Open end-of-day exceptions and configured recipients',
      output: 'Delivery receipt for the dated summary',
      validation: 'The recipient set and exception IDs are audited.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'resolve-eod',
      name: 'Recheck and resolve exceptions',
      description:
        'Close an exception after later source data proves the referral is scheduled.',
      system: 'Monitoring worker',
      next: 'Continue periodic monitoring',
      input: 'Open exceptions and refreshed source snapshots',
      output: 'Resolved exception or updated blocker',
      validation: 'Resolution requires explicit recorded scheduling evidence.',
      implementationStatus: 'partial',
    }),
  ],
}
