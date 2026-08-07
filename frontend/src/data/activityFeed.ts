import type { FlowOpsPageId } from './flowOps'
import type { ActivityEvent } from '../types'

export type ActivityStage = FlowOpsPageId | 'overview'

export function createInitialActivityFeed(): ActivityEvent[] {
  return [
    // Intake
    {
      id: 'act-intake-1',
      time: '10:18 AM',
      text: 'Patricia Johnson PDF validated · fingerprint recorded',
      stage: 'intake',
    },
    {
      id: 'act-intake-2',
      time: '10:11 AM',
      text: 'Robert Williams flagged probable duplicate · human review queued',
      stage: 'intake',
    },
    {
      id: 'act-intake-3',
      time: '9:58 AM',
      text: 'Linda Nguyen missing insurance highlighted for partner follow-up',
      stage: 'intake',
    },
    {
      id: 'act-intake-4',
      time: '9:44 AM',
      text: 'Maria Alvarez extraction complete · 7/7 fields ready for review',
      stage: 'intake',
    },
    // Handoff
    {
      id: 'act-handoff-1',
      time: '10:16 AM',
      text: 'Acknowledgement drafted for Oak Valley Hospital · James Carter',
      stage: 'handoff',
    },
    {
      id: 'act-handoff-2',
      time: '10:05 AM',
      text: 'Monday.com Master Sheet row prepared · Irene Cho',
      stage: 'handoff',
    },
    {
      id: 'act-handoff-3',
      time: '9:51 AM',
      text: 'DRK draft ready · face-sheet destination queued',
      stage: 'handoff',
    },
    {
      id: 'act-handoff-4',
      time: '9:33 AM',
      text: 'Handoff held · Evelyn Brooks phone still unclear',
      stage: 'handoff',
    },
    // Assignment
    {
      id: 'act-assign-1',
      time: '10:12 AM',
      text: 'Riverside ZIP matched Braxton Rickert · awaiting CM confirm',
      stage: 'assignment',
    },
    {
      id: 'act-assign-2',
      time: '10:08 AM',
      text: 'Carla Bustillo accepted Coastal LA assignment for Samuel Ortiz',
      stage: 'assignment',
    },
    {
      id: 'act-assign-3',
      time: '9:55 AM',
      text: 'No territory match · info-box manager notified for Helen Park',
      stage: 'assignment',
    },
    {
      id: 'act-assign-4',
      time: '9:40 AM',
      text: 'Two CM matches for Gardena ZIP · human selection opened',
      stage: 'assignment',
    },
    // Provider
    {
      id: 'act-provider-1',
      time: '10:14 AM',
      text: 'Company provider suggested for Thomas Reed · Downey territory',
      stage: 'provider',
    },
    {
      id: 'act-provider-2',
      time: '10:01 AM',
      text: 'Ambiguous Gardena coverage · two nearby providers queued for CM',
      stage: 'provider',
    },
    {
      id: 'act-provider-3',
      time: '9:47 AM',
      text: 'No provider coverage · Nicole review opened for Inland Empire case',
      stage: 'provider',
    },
    {
      id: 'act-provider-4',
      time: '9:29 AM',
      text: 'Provider selected · Referral sent to provider still unset',
      stage: 'provider',
    },
    // Scheduling
    {
      id: 'act-sched-1',
      time: '10:14 AM',
      text: 'Braxton Rickert confirmed provider window for Helen Park',
      stage: 'scheduling',
    },
    {
      id: 'act-sched-2',
      time: '10:02 AM',
      text: 'One-hour response timer started · Placentia route window offered',
      stage: 'scheduling',
    },
    {
      id: 'act-sched-3',
      time: '9:46 AM',
      text: 'No provider confirm within hour · alternate path flagged',
      stage: 'scheduling',
    },
    {
      id: 'act-sched-4',
      time: '9:28 AM',
      text: 'Route-aware windows prepared for Long Beach visit',
      stage: 'scheduling',
    },
    // End of day
    {
      id: 'act-eod-1',
      time: '9:41 AM',
      text: 'End-of-day scan queued · Daisy Trujillo owns two open blockers',
      stage: 'end-of-day',
    },
    {
      id: 'act-eod-2',
      time: '9:20 AM',
      text: 'Unscheduled referral list built · 4 exceptions for management',
      stage: 'end-of-day',
    },
    {
      id: 'act-eod-3',
      time: '9:05 AM',
      text: 'Scheduling-complete fields inconsistent · exception opened',
      stage: 'end-of-day',
    },
    {
      id: 'act-eod-4',
      time: '8:50 AM',
      text: 'Blank appointment date flagged after deadline',
      stage: 'end-of-day',
    },
    // Weekly
    {
      id: 'act-weekly-1',
      time: '9:36 AM',
      text: 'Missed visit counted · week 2 of 3 for noncompliance watch',
      stage: 'weekly',
    },
    {
      id: 'act-weekly-2',
      time: '9:18 AM',
      text: 'Healed status recorded · QA discharge review prepared',
      stage: 'weekly',
    },
    {
      id: 'act-weekly-3',
      time: '9:02 AM',
      text: 'Hold applied · patient removed from active weekly scheduling',
      stage: 'weekly',
    },
    {
      id: 'act-weekly-4',
      time: '8:44 AM',
      text: 'Return-ready patient re-entered weekly visit cycle',
      stage: 'weekly',
    },
    // Overview rollup
    {
      id: 'act-overview-1',
      time: '10:18 AM',
      text: 'Inbox sync complete · 7 referrals waiting confirmation',
      stage: 'overview',
    },
    {
      id: 'act-overview-2',
      time: '10:08 AM',
      text: 'Assignment + provider queues active across Coastal LA and Inland Empire',
      stage: 'overview',
    },
    {
      id: 'act-overview-3',
      time: '9:41 AM',
      text: 'Management exception list ready for end-of-day review',
      stage: 'overview',
    },
  ]
}

export function activityForStage(
  feed: ActivityEvent[],
  stage: ActivityStage,
  limit = 6,
): ActivityEvent[] {
  if (stage === 'overview') {
    const live = feed.filter((event) => event.time === 'Now')
    const overview = feed.filter((event) => event.stage === 'overview')
    const rest = feed.filter(
      (event) => event.stage !== 'overview' && event.time !== 'Now',
    )
    return [...live, ...overview, ...rest].slice(0, limit)
  }
  return feed.filter((event) => event.stage === stage).slice(0, limit)
}

export function stageActivityBlurb(stage: ActivityStage): string {
  switch (stage) {
    case 'intake':
      return 'Live intake events from today’s inbox run.'
    case 'handoff':
      return 'Acknowledgements, Monday.com, and DRK destination activity.'
    case 'assignment':
      return 'Territory matches, CM confirmations, and coverage exceptions.'
    case 'provider':
      return 'Provider suggestions, coverage gaps, and send-status updates.'
    case 'scheduling':
      return 'Route windows, response timers, and confirmation events.'
    case 'end-of-day':
      return 'Deadline scans, unscheduled referrals, and escalations.'
    case 'weekly':
      return 'Visit outcomes, holds, healed/expired, and return-ready events.'
    case 'overview':
      return 'Cross-stage operational events from today’s queues.'
  }
}
