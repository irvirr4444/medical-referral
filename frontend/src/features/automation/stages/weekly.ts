import type { AutomationStageDefinition } from '../types'
import { step } from './shared'

export const WEEKLY_STAGE: AutomationStageDefinition = {
  id: 'weekly',
  title: '7. Weekly visit cycle',
  shortTitle: 'Weekly visit cycle',
  purpose:
    'Answer the weekly clinical questions in order: seen, healed, expired, and on hold — then route the matching action.',
  trigger:
    'The weekly monitor runs for active linked patients with expected visit activity.',
  successDefinition:
    'Each active patient is marked seen or rescheduled after a miss, routed for healed or expired discharge review, or moved to holds.',
  implementationStatus: 'partial',
  microsteps: [
    step({
      id: 'patient-seen',
      name: 'Seen patients',
      description:
        'Confirm this week’s visit outcome. Seen patients stay on schedule; not-seen patients are marked and rescheduled, or escalated after three consecutive misses.',
      system: 'Monday.com / DRK / Microsoft Teams',
      next: 'Healed patients',
      input: 'Active linked patients and visit-status columns',
      output: 'Seen receipt, weekly reschedule, or noncompliance discharge review queue',
      validation:
        'Only explicit Seen or Not Seen values change the consecutive miss counter; three consecutive Not Seen visits require human discharge approval.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'wound-healed',
      name: 'Healed patients',
      description:
        'Route healed patients onto the provider → QA → discharge path. Human approval remains required.',
      system: 'QA / email / Monday.com',
      next: 'Expired patients',
      input: 'Patients with healed visit status',
      output: 'QA discharge path opened',
      validation:
        'Automation never discharges; QA and clinical approval remain required.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'patient-expired',
      name: 'Expired patients',
      description:
        'Remove expired patients from the weekly schedule and queue discharge approval.',
      system: 'Case manager / Monday.com / email',
      next: 'On hold patients',
      input: 'Patients with expired visit status',
      output: 'Removed from schedule pending DC approval',
      validation:
        'Human discharge approval remains required; no automatic discharge.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'patient-on-hold',
      name: 'On hold patients',
      description:
        'Move patients on hold (hospital, vacation, or other) to the holds team and holds list until they are ready to return.',
      system: 'Holds list / Monday.com',
      next: 'Continue the next weekly cycle',
      input: 'Patients with on-hold visit status',
      output: 'Hold tracking recorded with the holds team',
      validation:
        'Weekly visit monitoring pauses until the patient is ready to return to the cycle.',
      implementationStatus: 'partial',
    }),
  ],
}
