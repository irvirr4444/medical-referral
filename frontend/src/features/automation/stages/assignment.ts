import type { AutomationStageDefinition } from '../types'
import { step } from './shared'

export const ASSIGNMENT_STAGE: AutomationStageDefinition = {
  id: 'assignment',
  title: '3. Assignment',
  shortTitle: 'Assignment',
  purpose:
    "Assign complete referrals to the correct case manager by location. Route incomplete referrals to the referral source's marketer for follow-up.",
  trigger: 'An approved referral has completed its destination handoff.',
  successDefinition:
    'One eligible case manager or marketer is confirmed, or a clear exception is routed to a human.',
  implementationStatus: 'planned',
  microsteps: [
    step({
      id: 'load-assignment-context',
      name: 'Load patient, source, and completeness',
      description:
        'Collect patient location, facility, referral source, and current ownership.',
      system: 'Workflow database',
      next: 'Normalize the service location',
      input: 'Approved patient and referral links',
      output: 'Assignment context record',
      validation:
        'No assignment is attempted without a usable service location.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'normalize-location',
      name: 'Verify the service location',
      description:
        'Resolve the patient address or facility into a consistent territory input.',
      system: 'Location normalizer',
      next: 'Load territory rules',
      input: 'Patient address and facility address',
      output: 'Normalized city, ZIP code, and location type',
      validation: 'Facility and residence conflicts are preserved for review.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'load-territories',
      name: 'Load the current ownership rules',
      description: 'Read the current WCW owner and coverage configuration.',
      system: 'Assignment configuration',
      next: 'Match eligible owners',
      input: 'Versioned WCW territory mapping',
      output: 'Applicable coverage rules',
      validation: 'Every decision records the rule version used.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'match-owner',
      name: 'Find case-manager and marketer candidates',
      description:
        'Find case-manager and marketer candidates for the normalized location.',
      system: 'Assignment matcher',
      next: 'Classify the match',
      input: 'Location and territory rules',
      output: 'Ranked owner candidates with reasons',
      validation: 'Inactive or unavailable staff are excluded.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'classify-assignment',
      name: 'Choose the correct routing branch',
      description:
        'Send complete referrals toward case-manager assignment and missing-information follow-up toward the source marketer.',
      system: 'Assignment policy',
      next: 'Request human confirmation',
      input: 'Ranked owner candidates',
      output: 'Case-manager branch, marketer follow-up branch, or ownership exception',
      validation: 'Conflicts never auto-assign a patient.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'confirm-assignment',
      name: 'Confirm the responsible owner',
      description:
        'Present the recommendation and evidence to the responsible WCW employee.',
      system: 'Human approval',
      next: 'Write and verify ownership',
      input: 'Recommended owner and matching evidence',
      output: 'Approved owner or corrected selection',
      validation:
        'The final owner is always attributable to a person or approved rule.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'write-assignment',
      name: 'Record and verify the assignment',
      description:
        'Update the authorized systems and record the assignment event.',
      system: 'Monday / DRK adapters',
      next: 'Begin Provider selection',
      input: 'Confirmed owner',
      output: 'Verified ownership state and audit event',
      validation:
        'Partial writes create a retry for only the failed destination.',
      implementationStatus: 'planned',
    }),
  ],
}
