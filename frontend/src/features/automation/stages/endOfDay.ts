import type { AutomationStageDefinition } from '../types'
import { step } from './shared'

export const END_OF_DAY_STAGE: AutomationStageDefinition = {
  id: 'end-of-day',
  title: '6. End-of-day check',
  shortTitle: 'End-of-day check',
  purpose:
    'Identify every patient still unscheduled at day\'s end and escalate unresolved blockers to the appropriate team.',
  trigger:
    "The monitoring worker reaches the approved end-of-day cutoff in WCW's timezone.",
  successDefinition:
    'Each due referral is scheduled, assigned for follow-up, or escalated with a clear blocker.',
  implementationStatus: 'partial',
  microsteps: [
    step({
      id: 'start-eod-cycle',
      name: 'Start the end-of-day scheduling check',
      description:
        'Confirm the configured timezone, cutoff, and monitor health before evaluating patients.',
      system: 'Monitoring worker',
      next: 'Find patients missing an appointment',
      input: 'WCW cutoff configuration and worker heartbeat',
      output: 'One dated monitoring cycle',
      validation:
        'A stale or unhealthy source blocks conclusions and raises a monitoring alert.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'load-due-referrals',
      name: 'Find patients missing an appointment',
      description:
        'Select active referrals expected to have an appointment by the cutoff.',
      system: 'Workflow database',
      next: 'Identify the case manager and blocker',
      input: 'Active linked referrals and due-date rules',
      output: 'Bounded list of due referrals',
      validation:
        'Completed, discharged, and future-due referrals are excluded.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'read-eod-sources',
      name: 'Identify the case manager and blocker',
      description:
        'Read Monday.com and DRK to show who owns the patient and why scheduling is incomplete.',
      system: 'Monday and DRK readers',
      next: 'Notify the lead and case manager',
      input: 'Monday item and DRK chart identifiers',
      output: 'Assigned owner and scheduling blocker',
      validation:
        'Source failures remain distinct from an unscheduled patient.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'normalize-scheduling',
      name: 'Notify the lead and case manager',
      description:
        'Send the patient, owner, and missing scheduling details to the responsible lead and case manager.',
      system: 'Teams and notification service',
      next: 'Track the follow-up',
      input: 'Patient, assigned owner, and scheduling blocker',
      output: 'Follow-up request delivered',
      validation: 'The request is sent once to the correct patient owner.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'dedupe-eod-alerts',
      name: 'Track the follow-up',
      description:
        'Track whether the case manager resolves the blocker without sending duplicate reminders.',
      system: 'Follow-up tracker',
      next: 'Escalate unresolved cases',
      input: 'Follow-up request and patient scheduling status',
      output: 'Resolved follow-up or unresolved blocker',
      validation:
        'Only one active follow-up is kept per patient and scheduling day.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'create-eod-exceptions',
      name: 'Escalate unresolved cases',
      description:
        'Route cases the CM and lead cannot resolve to Nicole or upper management.',
      system: 'Management escalation',
      next: 'Verify the final scheduling status',
      input: 'Unresolved blocker and follow-up history',
      output: 'Management escalation with clear ownership',
      validation: 'Each unresolved patient is escalated once with supporting details.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'notify-eod',
      name: 'Verify the final scheduling status',
      description:
        'Recheck Monday.com and DRK after follow-up to confirm whether the patient is scheduled.',
      system: 'Monday and DRK readers',
      next: 'Move scheduled patients into the weekly cycle',
      input: 'Follow-up result and refreshed scheduling fields',
      output: 'Scheduled or still unresolved',
      validation: 'Only explicit appointment evidence marks a patient scheduled.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'resolve-eod',
      name: 'Move scheduled patients into the weekly cycle',
      description:
        'Close the scheduling follow-up and place confirmed patients into weekly visit tracking.',
      system: 'Monitoring worker',
      next: 'Begin weekly visit tracking',
      input: 'Verified appointment and patient record',
      output: 'Patient entered into the weekly visit cycle',
      validation: 'Only verified scheduled patients enter the weekly cycle.',
      implementationStatus: 'partial',
    }),
  ],
}
