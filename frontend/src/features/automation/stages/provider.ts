import type { AutomationStageDefinition } from '../types'
import { step } from './shared'

export const PROVIDER_STAGE: AutomationStageDefinition = {
  id: 'provider',
  title: '4. Provider selection',
  shortTitle: 'Provider selection',
  purpose: 'Select an approved provider for the patient location and care need.',
  trigger: 'The assigned owner is confirmed and the handoff is verified.',
  successDefinition: 'A provider is recorded, or a coverage gap has a named owner.',
  implementationStatus: 'planned',
  microsteps: [
    step({
      id: 'find-eligible-providers',
      name: 'Find Eligible Providers',
      description: 'Filter the active roster by service area and wound-care capability.',
      system: 'Provider rules',
      next: 'Select Best-Matched Provider',
      input: 'Location, care need, and active roster',
      output: 'Eligible providers',
      validation: 'Every exclusion has a visible reason.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'select-provider',
      name: 'Select Best-Matched Provider',
      description: 'Choose the strongest operational match or expose a coverage gap.',
      system: 'Provider matching',
      next: 'Record Provider Selection',
      input: 'Eligible providers',
      output: 'Recommended provider or coverage gap',
      validation: 'The ranking does not make a clinical decision.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'record-provider',
      name: 'Record Provider Selection',
      description: 'Choose a provider and write the selection into WCW systems.',
      system: 'Case manager / Monday.com / DRK',
      next: 'Begin Scheduling',
      input: 'Ranked provider choices',
      output: 'Verified provider fields',
      validation: 'Read-back must match the confirmed provider.',
      implementationStatus: 'planned',
    }),
  ],
}
