import type { AutomationStageDefinition } from '../types'
import { step } from './shared'

export const PROVIDER_STAGE: AutomationStageDefinition = {
  id: 'provider',
  title: '4. Provider selection',
  shortTitle: 'Provider selection',
  purpose:
    "Match each patient with an approved provider based on service area, care needs, and availability.",
  trigger:
    'The referral has an assigned WCW owner and a verified service location.',
  successDefinition:
    'A human confirms an eligible provider, or the lack of coverage is escalated with evidence.',
  implementationStatus: 'planned',
  microsteps: [
    step({
      id: 'load-provider-context',
      name: 'Load patient and service-area details',
      description:
        'Collect the patient location, wound-care needs, and assigned case manager.',
      system: 'Workflow database',
      next: 'Find approved providers serving the area',
      input: 'Assigned referral and clinical summary',
      output: 'Patient and service-area details',
      validation: 'Clinical source values remain linked to their evidence.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'load-provider-roster',
      name: 'Find approved providers serving the area',
      description:
        'Read current provider status and WCW-approved coverage data.',
      system: 'Provider roster adapter',
      next: 'Check provider eligibility',
      input: 'Versioned provider roster',
      output: 'Active provider candidates',
      validation:
        'The roster timestamp and source are visible to the reviewer.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'filter-providers',
      name: 'Check provider eligibility',
      description:
        'Filter candidates by territory, service capability, and confirmed business rules.',
      system: 'Provider rules',
      next: 'Rank suitable providers',
      input: 'Active providers and referral context',
      output: 'Eligible provider set with exclusion reasons',
      validation:
        'Unconfirmed payer or clinical assumptions cannot silently exclude a provider.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'rank-providers',
      name: 'Rank suitable providers',
      description:
        'Order eligible providers using explainable operational criteria.',
      system: 'Provider ranking',
      next: 'Identify coverage gaps',
      input: 'Eligible provider set',
      output: 'Ranked shortlist with location and coverage rationale',
      validation: 'Ranking does not make a clinical decision.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'classify-provider-result',
      name: 'Identify coverage gaps',
      description:
        'Identify clear matches, ambiguous coverage, and areas with no available provider.',
      system: 'Provider policy',
      next: 'Case manager confirms the provider',
      input: 'Ranked shortlist',
      output: 'Provider recommendation or coverage gap',
      validation:
        'Ambiguous and uncovered cases are sent to Nicole for human review.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'confirm-provider',
      name: 'Case manager confirms the provider',
      description:
        'Allow the responsible employee to approve or replace the recommendation.',
      system: 'Human approval',
      next: 'Record and verify the selected provider',
      input: 'Shortlist and selection evidence',
      output: 'Confirmed provider or management escalation',
      validation: 'The approving person and chosen reason are recorded.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'write-provider',
      name: 'Record and verify the selected provider',
      description:
        'Update the approved systems and create the provider-selection audit event.',
      system: 'Monday / DRK adapters',
      next: 'Begin Scheduling',
      input: 'Confirmed provider',
      output: 'Verified provider state',
      validation: 'A read-back confirms the expected provider value.',
      implementationStatus: 'planned',
    }),
  ],
}
