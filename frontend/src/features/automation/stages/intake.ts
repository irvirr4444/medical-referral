import type { AutomationStageDefinition } from '../types'
import { step } from './shared'

export const INTAKE_STAGE: AutomationStageDefinition = {
  id: 'intake',
  title: '1. Referral intake',
  shortTitle: 'Referral intake',
  purpose:
    'Verify every inbound referral PDF, capture the required patient information, and route missing or uncertain data for human follow-up.',
  trigger:
    'A new Outlook message reaches the monitored inbox with at least one PDF attachment.',
  successDefinition:
    'The referral is extracted, checked for missing fields and existing records, then completed after human confirmation.',
  implementationStatus: 'working',
  microsteps: [
    step({
      id: 'receive-referral',
      name: 'Receive referral in inbox',
      description:
        'Poll the monitored Outlook inbox and identify messages that may contain referrals.',
      system: 'Microsoft Graph / Outlook',
      next: 'Extract and verify referral details',
      input: 'Unread message: New wound care referral',
      output: 'Message and attachment metadata normalized for intake',
      validation:
        'The message has a stable Microsoft message ID and received timestamp.',
    }),
    step({
      id: 'extract-and-verify',
      name: 'Extract and verify referral details',
      description:
        'Extract the PDF into canonical referral JSON, score the seven required fields, and check the four-field minimum threshold.',
      system: 'Canonical PDF extractor + intake rules',
      next: 'Check Monday for existing patient',
      input: 'Referral PDF attachment',
      output:
        'Canonical referral with field completeness and threshold decision',
      validation:
        'Name, DOB, phone, and address must clear the threshold before duplicate checks continue.',
      duration: '2m 41s',
      exception: {
        input: 'PDF missing phone or address',
        output: 'Extraction complete · identity/contact incomplete',
        validation:
          'Missing minimum fields block Monday/DRK checks and destination writes.',
      },
    }),
    step({
      id: 'check-monday',
      name: 'Check Monday for existing patient',
      description:
        'Search existing Master Sheet items using normalized patient identity.',
      system: 'Monday.com reader',
      next: 'Search DRK for chart matches',
      input: 'Patient name and date of birth',
      output: 'No matching Monday.com candidate found',
      validation:
        'Name-only matches never authorize patient creation or blocking.',
      exception: {
        input: 'Incomplete identity',
        output: 'Monday duplicate search skipped',
        validation:
          'Search is marked indeterminate when identity is insufficient.',
      },
    }),
    step({
      id: 'check-drk',
      name: 'Check DRK for existing chart',
      description:
        'Check available DRK patient information before preparing a new chart action.',
      system: 'DRK reader',
      next: 'Referral partner contacted',
      input: 'Patient name and DOB',
      output: 'No exact DRK chart match found',
      validation:
        'Any candidate requires DOB confirmation before it can be treated as the same patient.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'confirm-referral-contacted',
      name: 'Referral partner contacted',
      description:
        'Confirm that the referral partner was contacted and outreach notes are captured.',
      system: 'DRK intake team',
      next: 'Begin the Handoff stage',
      input: 'Contact status, outreach note, and supporting intake context',
      output: 'Referral partner contact confirmed',
      validation:
        'Contact confirmation must be explicitly recorded before intake can be completed.',
      exception: {
        input: 'No documented partner contact yet',
        output: 'Contact confirmation pending',
        validation: 'The reviewer sees every blocker before responding.',
      },
    }),
  ],
}
