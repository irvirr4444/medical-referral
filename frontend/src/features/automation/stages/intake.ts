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
      next: 'Inspect attachments',
      input: 'Unread message: New wound care referral',
      output: 'Message and attachment metadata normalized for intake',
      validation:
        'The message has a stable Microsoft message ID and received timestamp.',
    }),
    step({
      id: 'validate-pdf',
      name: 'Validate PDF attachment',
      description:
        'Accept only attachments whose name and binary signature identify a real PDF.',
      system: 'Outlook adapter',
      next: 'Extract patient and referral details',
      input: 'synthetic-complete-referral.pdf, application/pdf',
      output: 'One accepted PDF attachment',
      validation:
        'Filename ends in .pdf and content starts with the PDF file signature.',
      exception: {
        input: 'synthetic-incomplete-referral.pdf, application/pdf',
        output: 'One accepted PDF attachment',
        validation:
          'The file is valid even though its clinical content is incomplete.',
      },
    }),
    step({
      id: 'extract-details',
      name: 'Extract patient and referral details',
      description:
        'Send the PDF through the canonical Anthropic Files API extractor.',
      system: 'Canonical PDF extractor',
      next: 'Verify evidence and required fields',
      input: 'Synthetic referral PDF',
      output:
        'Canonical referral JSON with patient, clinical, insurance, and source fields',
      validation:
        'The response must satisfy the referral schema before it is accepted.',
      duration: '2m 41s',
      exception: {
        input: 'Synthetic referral with no insurance section',
        output: 'Canonical referral JSON with insurance marked missing',
        validation:
          'Missing content remains null; the extractor does not invent a carrier.',
      },
    }),
    step({
      id: 'verify-required-fields',
      name: 'Verify 7 required fields',
      description:
        'Classify every required value as complete, explicitly absent, missing, or unclear.',
      system: 'Intake rules',
      next: 'Apply the minimum intake threshold',
      input: 'Canonical referral JSON and source evidence',
      output: '7 of 7 fields complete',
      validation:
        'Name, DOB, phone, address, agency, wound information, and insurance are evaluated separately.',
      exception: {
        input: 'Canonical JSON with insurance null',
        output: '6 of 7 complete; insurance missing',
        validation:
          'Missing insurance is surfaced as a gap rather than treated as complete.',
      },
    }),
    step({
      id: 'check-threshold',
      name: 'Check minimum threshold',
      description:
        'Check whether name, DOB, phone, and address are present before downstream preparation.',
      system: 'Intake planner',
      next: 'Check Monday and DRK for existing records',
      input: 'Four minimum identity/contact fields',
      output: 'Threshold met; duplicate checks allowed',
      validation: 'A missing minimum field blocks destination writes.',
      exception: {
        input: 'Name and DOB present; phone and address missing',
        output: 'Threshold not met; downstream writes blocked',
        validation: 'The plan records the exact missing threshold fields.',
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
      next: 'Confirm referral partner was contacted',
      input: 'Patient name and DOB',
      output: 'No exact DRK chart match found',
      validation:
        'Any candidate requires DOB confirmation before it can be treated as the same patient.',
      implementationStatus: 'partial',
    }),
    step({
      id: 'confirm-referral-contacted',
      name: 'Confirm referral partner was contacted',
      description:
        'Confirm that the referral partner was contacted and outreach notes are captured.',
      system: 'DRK intake team',
      next: 'Confirm information is correct',
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
    step({
      id: 'confirm-information-complete',
      name: 'Confirm information is correct and complete intake',
      description:
        'A DRK team member confirms extracted data accuracy and marks intake complete.',
      system: 'DRK intake team',
      next: 'Begin the Handoff stage',
      input: 'Extracted referral details, field checks, Monday/DRK checks, and contact confirmation',
      output: 'Referral Intake completed and ready for handoff',
      validation:
        'Intake is complete only when outreach is confirmed and the information is approved as accurate.',
      exception: {
        input: 'Contact or accuracy confirmation missing',
        output: 'Intake completion blocked',
        validation:
          'The run remains available for correction and later review.',
      },
    }),
  ],
}
