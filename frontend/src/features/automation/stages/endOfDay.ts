import type { AutomationStageDefinition } from '../types'
import { step } from './shared'

export const END_OF_DAY_STAGE: AutomationStageDefinition = {
  id: 'end-of-day',
  title: '5. End-of-day check',
  shortTitle: 'End-of-day check',
  purpose:
    'Confirm each due referral is scheduled in Monday.com, follow up with the case manager when it is not, and escalate unresolved cases to management.',
  trigger:
    'The end-of-day cutoff is reached for referrals that should already be scheduled.',
  successDefinition:
    'Each due referral is scheduled, resolved after case-manager follow-up, or escalated once to management.',
  implementationStatus: 'planned',
  microsteps: [
    step({
      id: 'check-scheduling-status',
      name: 'Check Scheduling Status',
      description:
        'Review due referrals against Monday.com scheduled status, appointment date, and scheduled complete.',
      system: 'Monday.com / monitoring worker',
      next: 'Follow Up with Case Manager',
      input: 'Due referrals and Monday Master Sheet scheduling columns',
      output: 'Scheduled, unscheduled, or inconsistent scheduling state',
      validation:
        'Only explicit Monday.com values determine whether the patient is scheduled.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'follow-up-case-manager',
      name: 'Follow Up with Case Manager',
      description:
        'When a due referral is not scheduled, the lead follows up with the assigned case manager on Teams.',
      system: 'Microsoft Teams / lead',
      next: 'Escalate Unresolved Cases',
      input: 'Unscheduled or inconsistent referrals and assigned case manager',
      output: 'Teams follow-up sent and response recorded',
      validation:
        'Follow-up is required before escalation when scheduling status is blank or conflicting.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'escalate-unresolved-cases',
      name: 'Escalate Unresolved Cases',
      description:
        'Escalate referrals the case manager or lead cannot resolve to Nicole and upper management by email and spreadsheet.',
      system: 'Email / management spreadsheet',
      next: 'Enter weekly visit monitoring',
      input: 'Unresolved unscheduled referrals after Teams follow-up',
      output: 'Management escalation recorded',
      validation:
        'Each unresolved patient appears once in the escalation email and tracking spreadsheet.',
      implementationStatus: 'planned',
    }),
  ],
}
