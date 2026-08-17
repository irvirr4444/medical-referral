import type { AutomationStageDefinition } from '../types'
import { step } from './shared'

export const PROVIDER_STAGE: AutomationStageDefinition = {
  id: 'provider',
  title: '4. Provider selection',
  shortTitle: 'Provider selection',
  purpose: 'Select an approved provider for the patient location and care need.',
  trigger: 'The case manager is assigned and the initial handoff records are complete.',
  successDefinition: 'A provider is recorded, or a coverage gap has a named owner.',
  implementationStatus: 'planned',
  microsteps: [
    step({
      id: 'select-provider',
      name: 'Select Provider',
      description: 'Filter the roster, show an AI recommendation, and let the case manager confirm or change it.',
      system: 'Provider rules / case manager',
      next: 'Confirm Provider Availability',
      input: 'Patient location, case-manager territory, and company-provider roster',
      output: 'Case-manager-selected provider or coverage gap',
      validation: 'No eligible provider routes to Nicole for review before discharge.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'confirm-provider-availability',
      name: 'Confirm Provider Availability',
      description: 'Contact the selected provider and wait up to one hour for availability confirmation.',
      system: 'Case manager / provider communication',
      next: 'Update Monday.com and DRK',
      input: 'Selected provider and patient scheduling context',
      output: 'Confirmed availability or case-manager placement decision',
      validation: 'A timed-out response remains visible and requires case-manager placement.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'update-monday-drk',
      name: 'Update Monday.com and DRK',
      description:
        'Write the confirmed or placed provider into the case-manager half of Monday.com and DRK.',
      system: 'Case manager / Monday.com / DRK',
      next: 'Begin Scheduling',
      input: 'Confirmed or placed provider',
      output: 'Monday.com and DRK records updated with the assigned provider',
      validation:
        'Provider name and NPI must match in Monday.com and DRK before scheduling starts.',
      implementationStatus: 'planned',
    }),
  ],
}
