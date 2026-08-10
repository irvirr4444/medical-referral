import type { AutomationStageDefinition } from '../types'
import { step } from './shared'

export const PROVIDER_STAGE: AutomationStageDefinition = {
  id: 'provider',
  title: '4. Provider selection',
  shortTitle: 'Provider selection',
  purpose:
    "Help the case manager select an approved provider for the patient's area and escalate unavailable coverage to Nicole for review.",
  trigger:
    'The referral has an assigned WCW owner and a verified service location.',
  successDefinition:
    'A human confirms an eligible provider, or the lack of coverage is escalated with evidence.',
  implementationStatus: 'planned',
  microsteps: [
    step({
      id: 'load-provider-context',
      name: 'Load provider-selection context',
      description:
        'Collect location, wound-service needs, payer context, and assignment.',
      system: 'Workflow database',
      next: 'Load the active provider roster',
      input: 'Assigned referral and clinical summary',
      output: 'Provider-selection context',
      validation: 'Clinical source values remain linked to their evidence.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'load-provider-roster',
      name: 'Load the active provider roster',
      description:
        'Read current provider status and WCW-approved coverage data.',
      system: 'Provider roster adapter',
      next: 'Apply eligibility filters',
      input: 'Versioned provider roster',
      output: 'Active provider candidates',
      validation:
        'The roster timestamp and source are visible to the reviewer.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'filter-providers',
      name: 'Apply eligibility filters',
      description:
        'Filter candidates by territory, service capability, and confirmed business rules.',
      system: 'Provider rules',
      next: 'Rank candidates',
      input: 'Active providers and referral context',
      output: 'Eligible provider set with exclusion reasons',
      validation:
        'Unconfirmed payer or clinical assumptions cannot silently exclude a provider.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'rank-providers',
      name: 'Rank provider candidates',
      description:
        'Order eligible providers using explainable operational criteria.',
      system: 'Provider ranking',
      next: 'Classify provider coverage',
      input: 'Eligible provider set',
      output: 'Ranked shortlist with location and coverage rationale',
      validation: 'Ranking does not make a clinical decision.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'classify-provider-result',
      name: 'Classify provider coverage',
      description: 'Identify clear, ambiguous, and no-coverage outcomes.',
      system: 'Provider policy',
      next: 'Request human selection',
      input: 'Ranked shortlist',
      output: 'One recommendation or a coverage exception',
      validation: 'Ambiguous and uncovered cases require human action.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'confirm-provider',
      name: 'Confirm the provider',
      description:
        'Allow the responsible employee to approve or replace the recommendation.',
      system: 'Human approval',
      next: 'Record and verify provider',
      input: 'Shortlist and selection evidence',
      output: 'Confirmed provider or management escalation',
      validation: 'The approving person and chosen reason are recorded.',
      implementationStatus: 'planned',
    }),
    step({
      id: 'write-provider',
      name: 'Record and verify provider',
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
