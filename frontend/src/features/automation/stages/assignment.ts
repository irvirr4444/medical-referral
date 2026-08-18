import type { AutomationStageDefinition } from '../types'
import { HANDOFF_STAGE } from './handoff'
import { step } from './shared'

const notifyStep = HANDOFF_STAGE.microsteps.find(
  (item) => item.id === 'notify-referral-source',
)!
const mondayStep = HANDOFF_STAGE.microsteps.find(
  (item) => item.id === 'create-monday-record',
)!
const drkStep = HANDOFF_STAGE.microsteps.find(
  (item) => item.id === 'create-update-drk',
)!

export const ASSIGNMENT_STAGE: AutomationStageDefinition = {
  id: 'assignment',
  title: '2. Assignment & handoff',
  shortTitle: 'Assignment & handoff',
  purpose:
    'Confirm the case manager, notify them, and prepare the approved referral in Monday.com and DRK.',
  trigger: 'Stage 1 is complete and the referral is ready to move forward.',
  successDefinition:
    'The case manager is confirmed and notified, the Monday.com record is prepared or verified, and the DRK form is ready for final human review.',
  implementationStatus: 'planned',
  microsteps: [
    step({
      id: 'assign-owner',
      name: 'Assign Case Manager',
      description:
        'Route complete referrals to a case manager and incomplete referrals to a marketer, then confirm the responsible owner.',
      system: 'Assignment rules / WCW assignment approval',
      next: 'Notify Case Manager',
      input: 'Service location, source, missing fields, recommended owner, and routing reason',
      output: 'Verified assignment',
      validation:
        'Conflicting territory matches are not auto-assigned. The selected owner is confirmed before referral notifications are sent.',
      implementationStatus: 'planned',
    }),
    {
      ...notifyStep,
      name: 'Notify Case Manager',
      next: 'Create Monday.com Record',
    },
    {
      ...mondayStep,
      next: 'Prepare DRK Chart',
    },
    {
      ...drkStep,
      name: 'Prepare DRK Chart',
      description:
        'Prefill the DRK form from the approved referral so a person can complete final review. The automation does not press Create.',
      next: 'Begin Provider Selection',
      example: {
        ...drkStep.example,
        outputs: [
          { label: 'Produced', value: 'DRK form ready for final human review' },
        ],
        validation:
          'The form is prepared for human review; unresolved identity matches block prefilling. Create remains human-controlled.',
      },
    },
  ],
}
